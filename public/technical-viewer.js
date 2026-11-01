/**
 * Technical viewer for the existing Weronika Three.js scene.
 * Models are bundled in technical-models.js so the page never downloads a 3D file.
 */
import { buildCatalog } from "./technical-models.js";

const CYAN = 0x3ad7ff;
const CYAN_DIM = 0x7fdfff;
const AMBER = 0xffb23a;
const AMBER_HOT = 0xffd27a;

export function createTechnicalController(THREE, { scene, camera, getSize }) {
  const root = new THREE.Group();
  root.visible = false;
  root.name = "technical-viewer";
  scene.add(root);

  const rig = new THREE.Group();
  rig.position.y = 0.15;
  root.add(rig);

  const grid = new THREE.GridHelper(8.5, 28, CYAN, 0x123848);
  grid.position.y = -1.15;
  const gridMat = Array.isArray(grid.material) ? grid.material[0] : grid.material;
  gridMat.transparent = true;
  gridMat.opacity = 0.45;
  root.add(grid);

  const polar = new THREE.Group();
  polar.position.y = -1.14;
  root.add(polar);
  for (let i = 1; i <= 4; i++) {
    const ring = new THREE.Mesh(
      new THREE.RingGeometry(i * 0.55, i * 0.55 + 0.012, 80),
      new THREE.MeshBasicMaterial({
        color: i % 2 ? CYAN : AMBER,
        transparent: true,
        opacity: 0.22,
        side: THREE.DoubleSide,
        depthWrite: false,
      }),
    );
    ring.rotation.x = -Math.PI / 2;
    polar.add(ring);
  }

  const scanRings = [];
  for (let i = 0; i < 3; i++) {
    const mesh = new THREE.Mesh(
      new THREE.TorusGeometry(1.15 + i * 0.28, 0.008, 8, 80),
      new THREE.MeshBasicMaterial({
        color: i === 1 ? AMBER : CYAN,
        transparent: true,
        opacity: 0.55,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    );
    root.add(mesh);
    scanRings.push(mesh);
  }

  const beam = new THREE.Mesh(
    new THREE.PlaneGeometry(3.4, 0.018),
    new THREE.MeshBasicMaterial({
      color: CYAN,
      transparent: true,
      opacity: 0.38,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  root.add(beam);

  const frame = new THREE.LineSegments(
    new THREE.EdgesGeometry(new THREE.BoxGeometry(2.7, 1.9, 2.7)),
    new THREE.LineBasicMaterial({ color: CYAN, transparent: true, opacity: 0.16 }),
  );
  frame.position.y = 0.2;
  root.add(frame);

  const keyLight = new THREE.DirectionalLight(0xfff1dc, 0.9);
  keyLight.position.set(3.2, 5.4, 4.2);
  const rimLight = new THREE.DirectionalLight(0x3ad7ff, 0.22);
  rimLight.position.set(-4, 2.2, -3);
  const fillLight = new THREE.PointLight(0xffb23a, 0.12, 14);
  fillLight.position.set(0, 1.4, 2.2);
  root.add(new THREE.AmbientLight(0x9ecfff, 0.34), keyLight, rimLight, fillLight);

  const models = buildCatalog(THREE);
  for (const model of Object.values(models)) {
    model.group.visible = false;
    rig.add(model.group);
  }

  let active = null;
  let requestedLabel = "";
  let fallback = false;
  let explodeTarget = 0;
  let explodeCurrent = 0;
  let previousTickTime = null;
  const scratch = new THREE.Vector3();
  let customGroup = null;

  function disposeAsset(object) {
    if (!object) return;
    object.traverse?.((node) => {
      if (node.geometry) node.geometry.dispose();
      const materials = Array.isArray(node.material) ? node.material : [node.material];
      for (const material of materials) {
        if (!material) continue;
        for (const value of Object.values(material)) {
          if (value?.isTexture) value.dispose();
        }
        material.dispose();
      }
    });
  }

  function discardCustom() {
    if (!customGroup) return;
    rig.remove(customGroup);
    disposeAsset(customGroup);
    customGroup = null;
  }

  function activateCustom(object, title, kind, partName, extra = {}) {
    discardCustom();
    for (const model of Object.values(models)) model.group.visible = false;
    customGroup = new THREE.Group();
    customGroup.name = `uploaded-${kind}`;
    customGroup.add(object);
    rig.add(customGroup);
    customGroup.updateWorldMatrix(true, true);
    const bounds = new THREE.Box3().setFromObject(object);
    const size = bounds.getSize(new THREE.Vector3());
    const center = customGroup.worldToLocal(bounds.getCenter(new THREE.Vector3()));
    if (Number.isFinite(size.x + size.y + size.z) && Math.max(size.x, size.y, size.z) > 0) {
      object.position.sub(center);
      const scale = 2.7 / Math.max(size.x, size.y, size.z);
      customGroup.scale.setScalar(scale);
    }
    const part = customGroup;
    part.userData.name = partName;
    part.userData.major = true;
    part.userData.home = part.position.clone();
    part.userData.explode = new THREE.Vector3(0, 0.12, 0);
    active = {
      kind,
      title,
      hindi: title,
      parts: [part],
      ...extra,
    };
    previousTickTime = null;
    requestedLabel = title;
    fallback = false;
    root.visible = true;
    rig.rotation.set(0.08, 0.62, 0);
    explodeTarget = 0;
    explodeCurrent = 0;
    return describe();
  }

  async function openVRMFile(file) {
    if (!file || !/\.vrm$/i.test(file.name) || file.size > 100 * 1024 * 1024) {
      throw new Error("Choose a VRM file under 100 MB.");
    }
    const data = await file.arrayBuffer();
    let loaderModule;
    let vrmModule;
    try {
      [loaderModule, vrmModule] = await Promise.all([
        import("https://cdn.jsdelivr.net/npm/three@0.185.1/examples/jsm/loaders/GLTFLoader.js"),
        import("https://cdn.jsdelivr.net/npm/@pixiv/three-vrm@3.5.5/lib/three-vrm.module.min.js"),
      ]);
    } catch (error) {
      throw new Error(
        `Could not load VRM support modules. Check your internet connection and try again. ${error instanceof Error ? error.message : ""}`.trim(),
      );
    }
    const { GLTFLoader } = loaderModule;
    const { VRMLoaderPlugin, VRMUtils } = vrmModule;
    if (typeof GLTFLoader !== "function" || typeof VRMLoaderPlugin !== "function") {
      throw new Error("VRM support did not initialize correctly. Refresh the page and try again.");
    }
    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));
    const gltf = await new Promise((resolve, reject) => {
      loader.parse(data, "", resolve, (error) => {
        reject(new Error(error?.message || "The selected file is not a readable VRM model."));
      });
    });
    const vrm = gltf.userData?.vrm;
    if (!vrm?.scene) {
      throw new Error(
        "The file opened as a 3D asset but has no recognized VRM avatar. Choose a valid .vrm file.",
      );
    }
    if (vrm.meta?.metaVersion === "0" || vrm.meta?.metaVersion === 0) VRMUtils.rotateVRM0(vrm);
    const title = file.name.replace(/\.vrm$/i, "").slice(0, 80) || "Uploaded VRM";
    return activateCustom(vrm.scene, title, "vrm", "VRM avatar", { vrm });
  }

  async function openGeneratedModelFile(file, title = "Generated 3D model") {
    if (!file || typeof file.arrayBuffer !== "function" || file.size > 80 * 1024 * 1024) {
      throw new Error("The generated model is empty or exceeds the 80 MB viewer limit.");
    }
    let GLTFLoader;
    try {
      ({ GLTFLoader } =
        await import("https://cdn.jsdelivr.net/npm/three@0.185.1/examples/jsm/loaders/GLTFLoader.js"));
    } catch (error) {
      throw new Error(
        `Could not load the 3D model viewer. Check your internet connection. ${error instanceof Error ? error.message : ""}`.trim(),
      );
    }
    const data = await file.arrayBuffer();
    const loader = new GLTFLoader();
    const gltf = await new Promise((resolve, reject) => {
      loader.parse(data, "", resolve, (error) => {
        reject(new Error(error?.message || "The generated model could not be opened."));
      });
    });
    const model = gltf.scene || gltf.scenes?.[0];
    if (!model) throw new Error("The generated GLB did not contain a 3D scene.");
    return activateCustom(
      model,
      title.slice(0, 80) || "Generated 3D model",
      "photo-model",
      "AI mesh",
    );
  }

  async function openPhotoFile(file) {
    const hasImageType = Boolean(file?.type?.startsWith("image/"));
    const hasImageExtension = /\.(?:avif|bmp|gif|jpe?g|png|webp)$/i.test(file?.name || "");
    if (!file || (!hasImageType && !hasImageExtension) || file.size > 25 * 1024 * 1024) {
      throw new Error("Choose a JPG, PNG, WebP, GIF, BMP, or AVIF image under 25 MB.");
    }
    let bitmap;
    try {
      bitmap = await createImageBitmap(file);
    } catch {
      throw new Error(
        "This image format could not be decoded by your browser. Try a JPG or PNG photo.",
      );
    }
    const ratio = bitmap.width / bitmap.height;
    const canvas = document.createElement("canvas");
    const maxSide = 1400;
    const reduction = Math.min(1, maxSide / Math.max(bitmap.width, bitmap.height));
    canvas.width = Math.max(1, Math.round(bitmap.width * reduction));
    canvas.height = Math.max(1, Math.round(bitmap.height * reduction));
    const context = canvas.getContext("2d", { willReadFrequently: true });
    if (!context) throw new Error("This browser could not prepare the uploaded photo.");
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close?.();

    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = 4;
    const maxDimension = 3.2;
    const width = ratio >= 1 ? maxDimension : maxDimension * ratio;
    const height = ratio >= 1 ? maxDimension / ratio : maxDimension;
    const columns = 160;
    const rows = Math.max(48, Math.min(220, Math.round((columns * height) / width)));
    const geometry = new THREE.BufferGeometry();
    const positions = [];
    const uvs = [];
    const indices = [];
    const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
    for (let y = 0; y <= rows; y++) {
      const v = y / rows;
      const py = Math.min(canvas.height - 1, Math.floor(v * canvas.height));
      for (let x = 0; x <= columns; x++) {
        const u = x / columns;
        const px = Math.min(canvas.width - 1, Math.floor(u * canvas.width));
        const offset = (py * canvas.width + px) * 4;
        const luminance =
          (pixels[offset] * 0.2126 + pixels[offset + 1] * 0.7152 + pixels[offset + 2] * 0.0722) /
          255;
        positions.push((u - 0.5) * width, (0.5 - v) * height, (luminance - 0.5) * 0.42);
        uvs.push(u, 1 - v);
      }
    }
    for (let y = 0; y < rows; y++) {
      for (let x = 0; x < columns; x++) {
        const a = y * (columns + 1) + x;
        const b = a + columns + 1;
        indices.push(a, b, a + 1, b, b + 1, a + 1);
      }
    }
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geometry.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
    geometry.setIndex(indices);
    geometry.computeVertexNormals();
    const relief = new THREE.Mesh(
      geometry,
      new THREE.MeshStandardMaterial({
        map: texture,
        roughness: 0.82,
        metalness: 0.08,
        side: THREE.DoubleSide,
      }),
    );
    relief.name = "Photo relief";
    const frame = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.BoxGeometry(width + 0.08, height + 0.08, 0.46)),
      new THREE.LineBasicMaterial({ color: CYAN, transparent: true, opacity: 0.72 }),
    );
    frame.position.z = -0.23;
    const photo = new THREE.Group();
    photo.add(relief, frame);
    const title = file.name.replace(/\.[^.]+$/, "").slice(0, 80) || "Uploaded photo";
    return activateCustom(photo, title, "photo-relief", "Photo relief");
  }

  function open(kind, label, isFallback) {
    discardCustom();
    const key = models[kind] ? kind : "machine";
    active = models[key];
    requestedLabel = label || active.title;
    fallback =
      Boolean(isFallback) || (key === "machine" && requestedLabel.toLowerCase() !== "machine");
    for (const model of Object.values(models)) model.group.visible = model === active;
    root.visible = true;
    rig.rotation.set(0.08, 0.62, 0);
    explodeTarget = 0.18;
    explodeCurrent = 0;
    return describe();
  }

  function close() {
    discardCustom();
    root.visible = false;
    active = null;
    explodeTarget = 0;
    explodeCurrent = 0;
  }

  function setExplode(amount) {
    explodeTarget = clamp(amount, 0, 1);
  }

  function nudgeExplode(delta) {
    setExplode(explodeTarget + delta);
  }

  function isOpen() {
    return root.visible && !!active;
  }

  function describe() {
    if (!active) return null;
    const display = fallback ? `${requestedLabel}` : active.title;
    return {
      kind: active.kind,
      title: active.title,
      hindi: active.hindi,
      displayTitle: display,
      requestedLabel,
      fallback,
      partCount: active.parts.length,
      parts: active.parts.map((part) => part.userData.name),
      explode: explodeTarget,
    };
  }

  function tick(time) {
    if (!isOpen()) return null;
    const delta = previousTickTime === null ? 0 : clamp(time - previousTickTime, 0, 0.1);
    previousTickTime = time;
    if (active?.vrm && delta > 0) active.vrm.update(delta);
    explodeCurrent += (explodeTarget - explodeCurrent) * 0.08;
    const amount = explodeCurrent;
    active.parts.forEach((part, index) => {
      const data = part.userData;
      scratch.copy(data.home).addScaledVector(data.explode, amount);
      scratch.y += Math.sin(time * 1.15 + index * 0.45) * 0.012 * amount;
      part.position.lerp(scratch, 0.22);
      if (data.spin) {
        const axis = data.spinAxis || "y";
        part.rotation[axis] += data.spin;
      }
    });
    rig.rotation.y = 0.62 + Math.sin(time * 0.15) * 0.04;

    scanRings.forEach((ring, index) => {
      ring.rotation.x = Math.PI / 2.4 + Math.sin(time * 0.3 + index) * 0.25;
      ring.rotation.z = time * (0.35 + index * 0.12);
      ring.position.y = Math.sin(time * 0.7 + index) * 0.72;
      ring.material.opacity = 0.28 + 0.28 * Math.abs(Math.sin(time * 1.4 + index));
    });
    beam.position.y = Math.sin(time * 0.85) * 0.85;
    beam.material.opacity = 0.22 + 0.2 * Math.abs(Math.sin(time * 1.6));
    grid.material.opacity = 0.32 + 0.08 * Math.sin(time * 0.8);

    return status(time);
  }

  function status(time) {
    const size = getSize();
    const labels = [];
    if (active && size.width && size.height) {
      active.parts.forEach((part) => {
        const show = part.userData.major || explodeCurrent > 0.22;
        if (!show) return;
        part.getWorldPosition(scratch);
        scratch.project(camera);
        if (scratch.z > 1) return;
        labels.push({
          name: part.userData.name,
          x: (scratch.x * 0.5 + 0.5) * size.width,
          y: (-scratch.y * 0.5 + 0.5) * size.height,
        });
      });
    }
    return {
      ...describe(),
      explode: explodeCurrent,
      scan: Math.round((time * 48) % 360),
      labels,
    };
  }

  return {
    open,
    openVRMFile,
    openGeneratedModelFile,
    openPhotoFile,
    close,
    setExplode,
    nudgeExplode,
    isOpen,
    tick,
    describe,
    getStatus: () => (isOpen() ? status(performance.now() / 1000) : null),
  };
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}
