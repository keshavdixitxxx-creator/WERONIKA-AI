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

  const keyLight = new THREE.DirectionalLight(0xfff1dc, 1.45);
  keyLight.position.set(3.2, 5.4, 4.2);
  const rimLight = new THREE.DirectionalLight(0x3ad7ff, 0.7);
  rimLight.position.set(-4, 2.2, -3);
  const fillLight = new THREE.PointLight(0xffb23a, 0.55, 14);
  fillLight.position.set(0, 1.4, 2.2);
  root.add(new THREE.AmbientLight(0x9ecfff, 0.55), keyLight, rimLight, fillLight);

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
  const scratch = new THREE.Vector3();

  function open(kind, label, isFallback) {
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
