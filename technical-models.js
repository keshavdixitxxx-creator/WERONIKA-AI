/**
 * Bundled solid models for the technical viewer.
 * Built in code so the page never downloads a 3D file.
 * The armor suit is an original design, not a film character asset.
 */

function materials(THREE) {
  const make = (color, metal, rough, extra = {}) =>
    new THREE.MeshStandardMaterial({
      color,
      metalness: metal,
      roughness: rough,
      ...extra,
    });
  return {
    paint: (color) => make(color, 0.58, 0.34),
    metal: (color) => make(color, 0.86, 0.22),
    rubber: (color = 0x171717) => make(color, 0.06, 0.92),
    glass: (color = 0x9adfff) =>
      make(color, 0.08, 0.06, { transparent: true, opacity: 0.42, depthWrite: false }),
    glow: (color) => make(color, 0.15, 0.3, { emissive: color, emissiveIntensity: 0.9 }),
    cloth: (color) => make(color, 0.04, 0.82),
  };
}

function shell(THREE, kind, title, hindi) {
  return { kind, title, hindi, group: new THREE.Group(), parts: [] };
}

function place(THREE, model, name, object, x, y, z, ex, ey, ez, major = false) {
  const spin = object.userData && object.userData.spin;
  const spinAxis = object.userData && object.userData.spinAxis;
  object.position.set(x, y, z);
  object.userData = {
    name,
    home: new THREE.Vector3(x, y, z),
    explode: new THREE.Vector3(ex, ey, ez),
    major,
  };
  if (spin) {
    object.userData.spin = spin;
    object.userData.spinAxis = spinAxis || "y";
  }
  model.parts.push(object);
  model.group.add(object);
  return object;
}

function box(THREE, mat, w, h, d) {
  return new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
}

function cyl(THREE, mat, radiusTop, radiusBottom, height, segments = 16) {
  return new THREE.Mesh(new THREE.CylinderGeometry(radiusTop, radiusBottom, height, segments), mat);
}

function sphere(THREE, mat, radius, w = 18, h = 12) {
  return new THREE.Mesh(new THREE.SphereGeometry(radius, w, h), mat);
}

function wheel(THREE, mat, radius = 0.23) {
  const group = new THREE.Group();
  const tire = new THREE.Mesh(new THREE.TorusGeometry(radius, radius * 0.32, 12, 28), mat.rubber());
  tire.rotation.y = Math.PI / 2;
  const rim = new THREE.Mesh(
    new THREE.CylinderGeometry(radius * 0.62, radius * 0.62, radius * 0.28, 18),
    mat.metal(0xd5dbe3),
  );
  rim.rotation.z = Math.PI / 2;
  const hub = new THREE.Mesh(new THREE.CylinderGeometry(radius * 0.18, radius * 0.18, radius * 0.34, 10), mat.metal(0x8d949c));
  hub.rotation.z = Math.PI / 2;
  group.add(tire, rim, hub);
  return group;
}

export function buildCatalog(THREE) {
  return {
    car: buildCar(THREE),
    bike: buildBike(THREE),
    armor: buildArmor(THREE),
    helicopter: buildHelicopter(THREE),
    plane: buildPlane(THREE),
    ship: buildShip(THREE),
    robot: buildRobot(THREE),
    machine: buildMachine(THREE),
  };
}

function buildCar(THREE) {
  const mat = materials(THREE);
  const model = shell(THREE, "car", "Car", "कार");
  const body = mat.paint(0x1a4f86);
  const trim = mat.metal(0xc5ccd4);
  place(THREE, model, "Chassis", box(THREE, body, 1.85, 0.28, 0.82), 0, 0.28, 0, 0, -0.34, 0, true);
  const cabin = box(THREE, body, 0.86, 0.38, 0.74);
  place(THREE, model, "Cabin", cabin, -0.08, 0.56, 0, 0, 0.42, 0, true);
  const hood = box(THREE, body, 0.58, 0.1, 0.76);
  hood.rotation.z = -0.08;
  place(THREE, model, "Hood", hood, 0.62, 0.4, 0, 0.46, 0.12, 0, true);
  place(THREE, model, "Trunk", box(THREE, body, 0.4, 0.12, 0.74), -0.74, 0.4, 0, -0.42, 0.1, 0, true);
  place(THREE, model, "Windshield", box(THREE, mat.glass(), 0.05, 0.32, 0.66), 0.32, 0.62, 0, 0.18, 0.36, 0, false);
  place(THREE, model, "Rear glass", box(THREE, mat.glass(), 0.05, 0.26, 0.62), -0.48, 0.6, 0, -0.16, 0.32, 0, false);
  place(THREE, model, "Door left", box(THREE, body, 0.5, 0.3, 0.04), -0.02, 0.42, 0.4, 0, 0.06, 0.55, true);
  place(THREE, model, "Door right", box(THREE, body, 0.5, 0.3, 0.04), -0.02, 0.42, -0.4, 0, 0.06, -0.55, true);
  place(THREE, model, "Front bumper", box(THREE, trim, 0.08, 0.12, 0.84), 0.96, 0.24, 0, 0.4, 0, 0, false);
  place(THREE, model, "Rear bumper", box(THREE, trim, 0.08, 0.12, 0.82), -0.96, 0.24, 0, -0.38, 0, 0, false);
  place(THREE, model, "Grille", box(THREE, mat.metal(0x2a3138), 0.04, 0.14, 0.36), 0.98, 0.34, 0, 0.48, 0.04, 0, false);
  place(THREE, model, "Headlight left", box(THREE, mat.glow(0xffe1a3), 0.05, 0.07, 0.14), 0.96, 0.34, 0.26, 0.42, 0.06, 0.16, false);
  place(THREE, model, "Headlight right", box(THREE, mat.glow(0xffe1a3), 0.05, 0.07, 0.14), 0.96, 0.34, -0.26, 0.42, 0.06, -0.16, false);
  place(THREE, model, "Mirror left", box(THREE, body, 0.08, 0.05, 0.12), 0.22, 0.58, 0.42, 0.08, 0.16, 0.28, false);
  place(THREE, model, "Mirror right", box(THREE, body, 0.08, 0.05, 0.12), 0.22, 0.58, -0.42, 0.08, 0.16, -0.28, false);
  const hubs = [
    ["Wheel front left", 0.58, 0.42],
    ["Wheel front right", 0.58, -0.42],
    ["Wheel rear left", -0.58, 0.42],
    ["Wheel rear right", -0.58, -0.42],
  ];
  for (const [name, x, z] of hubs) {
    place(THREE, model, name, wheel(THREE, mat, 0.22), x, 0.22, z, 0, -0.04, z > 0 ? 0.5 : -0.5, true);
  }
  return model;
}

function buildBike(THREE) {
  const mat = materials(THREE);
  const model = shell(THREE, "bike", "Motorcycle", "बाइक");
  const frame = mat.paint(0xb4232a);
  const dark = mat.metal(0x2c3138);
  place(THREE, model, "Front wheel", wheel(THREE, mat, 0.3), 0.78, 0.3, 0, 0.55, 0, 0, true);
  place(THREE, model, "Rear wheel", wheel(THREE, mat, 0.3), -0.78, 0.3, 0, -0.55, 0, 0, true);
  const tank = sphere(THREE, frame, 0.2, 16, 10);
  tank.scale.set(1.3, 0.7, 0.7);
  place(THREE, model, "Fuel tank", tank, 0.12, 0.62, 0, 0.08, 0.36, 0, true);
  place(THREE, model, "Seat", box(THREE, mat.cloth(0x1c1c1c), 0.42, 0.08, 0.16), -0.22, 0.66, 0, -0.12, 0.34, 0, true);
  place(THREE, model, "Engine", box(THREE, dark, 0.34, 0.26, 0.2), 0.02, 0.36, 0, 0, -0.28, 0, true);
  const fork = cyl(THREE, mat.metal(0xd7dde6), 0.025, 0.025, 0.52, 8);
  place(THREE, model, "Front fork", fork, 0.78, 0.58, 0, 0.28, 0.18, 0, true);
  place(THREE, model, "Handlebar", box(THREE, mat.metal(0xd7dde6), 0.08, 0.05, 0.5), 0.74, 0.86, 0, 0.2, 0.4, 0, true);
  const exhaust = cyl(THREE, mat.metal(0xb7b0a4), 0.045, 0.055, 0.7, 10);
  exhaust.rotation.z = Math.PI / 2;
  place(THREE, model, "Exhaust", exhaust, -0.28, 0.22, 0.16, -0.2, -0.16, 0.28, false);
  place(THREE, model, "Swingarm", box(THREE, dark, 0.5, 0.05, 0.08), -0.36, 0.32, 0, -0.2, -0.08, 0, false);
  place(THREE, model, "Headlight", sphere(THREE, mat.glow(0xffe1a3), 0.07), 0.9, 0.7, 0, 0.36, 0.16, 0, false);
  place(THREE, model, "Tail", box(THREE, frame, 0.18, 0.08, 0.12), -0.58, 0.58, 0, -0.32, 0.16, 0, false);
  return model;
}

function buildArmor(THREE) {
  const mat = materials(THREE);
  const model = shell(THREE, "armor", "Armor suit", "कवच");
  const red = mat.paint(0xb4232a);
  const gold = mat.metal(0xd4a24a);
  place(THREE, model, "Helmet", box(THREE, gold, 0.3, 0.32, 0.3), 0, 0.92, 0, 0, 0.5, 0, true);
  place(THREE, model, "Visor", box(THREE, mat.glow(0x7fdfff), 0.22, 0.06, 0.04), 0, 0.94, 0.15, 0, 0.5, 0.22, false);
  place(THREE, model, "Chest", box(THREE, red, 0.48, 0.42, 0.26), 0, 0.48, 0, 0, 0.12, 0, true);
  place(THREE, model, "Chest core", cyl(THREE, mat.glow(0x9adfff), 0.07, 0.07, 0.06, 16), 0, 0.5, 0.14, 0, 0.12, 0.28, true);
  place(THREE, model, "Belt", box(THREE, gold, 0.36, 0.1, 0.22), 0, 0.22, 0, 0, -0.08, 0, false);
  place(THREE, model, "Pauldron left", sphere(THREE, gold, 0.12), 0.3, 0.66, 0, 0.28, 0.18, 0, false);
  place(THREE, model, "Pauldron right", sphere(THREE, gold, 0.12), -0.3, 0.66, 0, -0.28, 0.18, 0, false);
  place(THREE, model, "Arm left", box(THREE, red, 0.12, 0.36, 0.12), 0.38, 0.4, 0, 0.55, 0.04, 0, true);
  place(THREE, model, "Arm right", box(THREE, red, 0.12, 0.36, 0.12), -0.38, 0.4, 0, -0.55, 0.04, 0, true);
  place(THREE, model, "Gauntlet left", box(THREE, gold, 0.12, 0.16, 0.12), 0.38, 0.12, 0, 0.7, -0.12, 0, false);
  place(THREE, model, "Gauntlet right", box(THREE, gold, 0.12, 0.16, 0.12), -0.38, 0.12, 0, -0.7, -0.12, 0, false);
  place(THREE, model, "Thigh left", box(THREE, red, 0.14, 0.32, 0.14), 0.12, 0.02, 0, 0.2, -0.16, 0, true);
  place(THREE, model, "Thigh right", box(THREE, red, 0.14, 0.32, 0.14), -0.12, 0.02, 0, -0.2, -0.16, 0, true);
  place(THREE, model, "Boot left", box(THREE, gold, 0.14, 0.28, 0.18), 0.12, -0.28, 0.02, 0.24, -0.42, 0.06, true);
  place(THREE, model, "Boot right", box(THREE, gold, 0.14, 0.28, 0.18), -0.12, -0.28, 0.02, -0.24, -0.42, 0.06, true);
  place(THREE, model, "Back pack", box(THREE, mat.metal(0x8a929a), 0.28, 0.28, 0.12), 0, 0.5, -0.18, 0, 0.16, -0.36, true);
  const thrusterL = cyl(THREE, mat.glow(0xffb23a), 0.04, 0.05, 0.16, 10);
  const thrusterR = cyl(THREE, mat.glow(0xffb23a), 0.04, 0.05, 0.16, 10);
  place(THREE, model, "Thruster left", thrusterL, 0.08, 0.42, -0.26, 0.1, 0.1, -0.48, false);
  place(THREE, model, "Thruster right", thrusterR, -0.08, 0.42, -0.26, -0.1, 0.1, -0.48, false);
  return model;
}

function rotor(THREE, mat, length, width) {
  const group = new THREE.Group();
  const bladeMat = mat.metal(0xd7dde6);
  for (let i = 0; i < 2; i++) {
    const blade = new THREE.Mesh(new THREE.BoxGeometry(length, 0.018, width), bladeMat);
    blade.rotation.y = (i * Math.PI) / 2;
    group.add(blade);
  }
  group.add(new THREE.Mesh(new THREE.CylinderGeometry(0.045, 0.045, 0.05, 12), mat.metal(0x8d949c)));
  return group;
}

function buildHelicopter(THREE) {
  const mat = materials(THREE);
  const model = shell(THREE, "helicopter", "Helicopter", "हेलीकॉप्टर");
  const body = mat.paint(0x2f6b45);
  const cabin = sphere(THREE, mat.glass(0xb7e7ff), 0.32, 20, 14);
  cabin.scale.set(1.15, 0.85, 0.9);
  place(THREE, model, "Cabin", cabin, 0.28, 0.32, 0, 0.2, 0.28, 0, true);
  place(THREE, model, "Fuselage", box(THREE, body, 0.7, 0.32, 0.36), -0.05, 0.28, 0, 0, 0.08, 0, true);
  place(THREE, model, "Tail boom", box(THREE, body, 0.95, 0.1, 0.1), -0.85, 0.36, 0, -0.45, 0.12, 0, true);
  place(THREE, model, "Tail fin", box(THREE, body, 0.08, 0.28, 0.22), -1.28, 0.5, 0, -0.55, 0.28, 0, true);
  const mast = cyl(THREE, mat.metal(0xd7dde6), 0.03, 0.03, 0.16, 8);
  place(THREE, model, "Rotor mast", mast, 0.05, 0.58, 0, 0, 0.4, 0, false);
  const main = rotor(THREE, mat, 0.85, 0.08);
  main.userData.spin = 0.18;
  main.userData.spinAxis = "y";
  place(THREE, model, "Main rotor", main, 0.05, 0.68, 0, 0, 0.55, 0, true);
  const tail = rotor(THREE, mat, 0.18, 0.04);
  tail.userData.spin = 0.32;
  tail.userData.spinAxis = "x";
  place(THREE, model, "Tail rotor", tail, -1.32, 0.5, 0.12, -0.6, 0.2, 0.2, false);
  place(THREE, model, "Skid left", box(THREE, mat.metal(0x8d949c), 0.7, 0.03, 0.04), 0.05, 0.02, 0.2, 0, -0.22, 0.28, false);
  place(THREE, model, "Skid right", box(THREE, mat.metal(0x8d949c), 0.7, 0.03, 0.04), 0.05, 0.02, -0.2, 0, -0.22, -0.28, false);
  place(THREE, model, "Engine housing", box(THREE, mat.metal(0x3a4148), 0.28, 0.14, 0.22), -0.12, 0.48, 0, -0.08, 0.28, 0, false);
  return model;
}

function buildPlane(THREE) {
  const mat = materials(THREE);
  const model = shell(THREE, "plane", "Plane", "विमान");
  const body = mat.paint(0xe8eef2);
  const accent = mat.paint(0x1a4f86);
  const fuse = cyl(THREE, body, 0.16, 0.2, 1.7, 18);
  fuse.rotation.z = Math.PI / 2;
  place(THREE, model, "Fuselage", fuse, 0, 0.32, 0, 0, 0.08, 0, true);
  const nose = sphere(THREE, body, 0.16, 16, 12);
  nose.scale.set(1.3, 0.9, 0.9);
  place(THREE, model, "Nose", nose, 0.9, 0.32, 0, 0.4, 0.08, 0, true);
  place(THREE, model, "Cockpit", sphere(THREE, mat.glass(), 0.12, 14, 10), 0.55, 0.44, 0, 0.22, 0.28, 0, false);
  place(THREE, model, "Wing left", box(THREE, accent, 0.34, 0.04, 1.15), 0.05, 0.3, 0.62, 0, 0.08, 0.7, true);
  place(THREE, model, "Wing right", box(THREE, accent, 0.34, 0.04, 1.15), 0.05, 0.3, -0.62, 0, 0.08, -0.7, true);
  place(THREE, model, "Tail fin", box(THREE, accent, 0.08, 0.32, 0.28), -0.78, 0.52, 0, -0.36, 0.36, 0, true);
  place(THREE, model, "Stabilizer left", box(THREE, accent, 0.16, 0.03, 0.32), -0.72, 0.4, 0.22, -0.28, 0.16, 0.24, false);
  place(THREE, model, "Stabilizer right", box(THREE, accent, 0.16, 0.03, 0.32), -0.72, 0.4, -0.22, -0.28, 0.16, -0.24, false);
  const engineL = cyl(THREE, mat.metal(0x8d949c), 0.08, 0.09, 0.28, 14);
  engineL.rotation.z = Math.PI / 2;
  const engineR = cyl(THREE, mat.metal(0x8d949c), 0.08, 0.09, 0.28, 14);
  engineR.rotation.z = Math.PI / 2;
  place(THREE, model, "Engine left", engineL, 0.12, 0.22, 0.42, 0.12, -0.08, 0.36, true);
  place(THREE, model, "Engine right", engineR, 0.12, 0.22, -0.42, 0.12, -0.08, -0.36, true);
  return model;
}

function buildShip(THREE) {
  const mat = materials(THREE);
  const model = shell(THREE, "ship", "Ship", "जहाज");
  const hullMat = mat.paint(0x16324f);
  const hull = box(THREE, hullMat, 2.1, 0.28, 0.52);
  place(THREE, model, "Hull", hull, 0, 0.08, 0, 0, -0.28, 0, true);
  const bow = box(THREE, hullMat, 0.36, 0.2, 0.28);
  bow.rotation.y = 0.4;
  place(THREE, model, "Bow", bow, 1.12, 0.12, 0, 0.48, -0.12, 0, true);
  place(THREE, model, "Deck", box(THREE, mat.paint(0xd7c7a1), 1.7, 0.05, 0.46), -0.05, 0.24, 0, 0, 0.08, 0, false);
  place(THREE, model, "Bridge", box(THREE, mat.paint(0xf4f7f8), 0.42, 0.32, 0.34), -0.15, 0.42, 0, -0.08, 0.36, 0, true);
  place(THREE, model, "Bridge windows", box(THREE, mat.glass(), 0.36, 0.1, 0.04), -0.15, 0.48, 0.17, -0.08, 0.36, 0.22, false);
  place(THREE, model, "Funnel", cyl(THREE, mat.paint(0xb4232a), 0.08, 0.1, 0.28, 12), -0.42, 0.5, 0, -0.16, 0.42, 0, true);
  place(THREE, model, "Radar mast", cyl(THREE, mat.metal(0xd7dde6), 0.015, 0.015, 0.36, 8), 0.05, 0.7, 0, 0.04, 0.55, 0, false);
  place(THREE, model, "Lifeboat left", box(THREE, mat.paint(0xf0a04b), 0.22, 0.06, 0.08), 0.28, 0.32, 0.22, 0.12, 0.16, 0.32, false);
  place(THREE, model, "Lifeboat right", box(THREE, mat.paint(0xf0a04b), 0.22, 0.06, 0.08), 0.28, 0.32, -0.22, 0.12, 0.16, -0.32, false);
  place(THREE, model, "Anchor", box(THREE, mat.metal(0x8d949c), 0.06, 0.1, 0.04), 1.02, 0.16, 0, 0.42, -0.04, 0, false);
  return model;
}

function buildRobot(THREE) {
  const mat = materials(THREE);
  const model = shell(THREE, "robot", "Robot", "रोबोट");
  const shellMat = mat.metal(0xb7c3ce);
  const accent = mat.paint(0x1a4f86);
  place(THREE, model, "Head", box(THREE, shellMat, 0.3, 0.28, 0.26), 0, 0.92, 0, 0, 0.46, 0, true);
  place(THREE, model, "Eyes", box(THREE, mat.glow(0x7fdfff), 0.16, 0.04, 0.03), 0, 0.94, 0.13, 0, 0.46, 0.18, false);
  place(THREE, model, "Torso", box(THREE, accent, 0.42, 0.46, 0.24), 0, 0.5, 0, 0, 0.08, 0, true);
  place(THREE, model, "Arm left", box(THREE, shellMat, 0.1, 0.42, 0.1), 0.32, 0.46, 0, 0.48, 0.04, 0, true);
  place(THREE, model, "Arm right", box(THREE, shellMat, 0.1, 0.42, 0.1), -0.32, 0.46, 0, -0.48, 0.04, 0, true);
  place(THREE, model, "Leg left", box(THREE, shellMat, 0.12, 0.42, 0.12), 0.1, 0.02, 0, 0.18, -0.28, 0, true);
  place(THREE, model, "Leg right", box(THREE, shellMat, 0.12, 0.42, 0.12), -0.1, 0.02, 0, -0.18, -0.28, 0, true);
  place(THREE, model, "Foot left", box(THREE, mat.metal(0x6d757d), 0.14, 0.05, 0.2), 0.1, -0.2, 0.03, 0.18, -0.4, 0.06, false);
  place(THREE, model, "Foot right", box(THREE, mat.metal(0x6d757d), 0.14, 0.05, 0.2), -0.1, -0.2, 0.03, -0.18, -0.4, 0.06, false);
  return model;
}

function buildMachine(THREE) {
  const mat = materials(THREE);
  const model = shell(THREE, "machine", "Machine", "मशीन");
  place(THREE, model, "Base", box(THREE, mat.metal(0x8d949c), 1.2, 0.1, 0.8), 0, -0.2, 0, 0, -0.28, 0, true);
  place(THREE, model, "Housing", box(THREE, mat.paint(0x1a4f86), 0.8, 0.42, 0.55), 0, 0.16, 0, 0, 0.28, 0, true);
  const drum = cyl(THREE, mat.metal(0xd7dde6), 0.16, 0.16, 0.7, 18);
  drum.rotation.z = Math.PI / 2;
  place(THREE, model, "Drum", drum, 0, 0.16, 0, 0.4, 0.08, 0, true);
  place(THREE, model, "Panel", box(THREE, mat.glow(0xffb23a), 0.28, 0.18, 0.04), 0.22, 0.46, 0.26, 0.16, 0.36, 0.28, true);
  place(THREE, model, "Hatch", box(THREE, mat.paint(0x2c3138), 0.22, 0.28, 0.04), -0.4, 0.16, 0, -0.4, 0.06, 0, false);
  return model;
}
