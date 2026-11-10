import * as THREE from 'three';
import { smoothstep, distSegPoint } from '../engine/mathx.js';
import { ENV_STORM_NIGHT } from '../engine/environments.js';

// SEEPGAON (placeholder art): a small fishing village on a hill. The stone lighthouse "Diya-Ghar"
// stands in a walled yard on top; a lane winds down through the houses to Veer's home near the beach.
// North is -Z (lighthouse), south is +Z (home). This file is the storm-night version for Mission 0.

const YARD = { x: 0, z: -42 };   // lighthouse centre
const PLATEAU = 9.4;             // height of the flattened yard
const TOWER_H = 16;

// Named spots that missions use.
export const SEEPGAON = {
  home: { x: -4.5, z: 39.5 },
  porch: { x: -6, z: 44 },             // Dadaji's compass hangs here
  door: { x: 0, z: -37.3 },            // lighthouse door
  gate: { x: 0, z: -29 },              // just outside the yard
  shed: { x: -10, z: 22.4 },           // boat shed front: Dadaji's tin box
  island: { x: -380, z: 250 },         // the island the brass compass points to (open sea, south-west)
  lampTop: { x: 0, y: PLATEAU + TOWER_H + 1.3, z: -42 },
};

// The lane (used only to paint the ground so players can read the way).
const LANE = [[-4, 39], [-3, 30], [-2, 20], [2, 13], [6.5, 8], [5, 0], [5, -10], [1, -20], [0, -31], [0, -38]];

function heightAt(x, z) {
  const r = Math.hypot(x, z + 5);
  const land = 1.5 - 4.5 * smoothstep(46, 74, r);
  const hill = 8 * Math.exp(-(x * x + (z + 40) ** 2) / 900);
  const bumps = 0.25 * Math.sin(x * 0.17) * Math.cos(z * 0.14) * (1 - smoothstep(40, 60, r));
  const k = 1 - smoothstep(11, 17, Math.hypot(x - YARD.x, z - YARD.z)); // flatten the yard
  return (land + hill + bumps) * (1 - k) + PLATEAU * k;
}

export const seepgaon = {
  id: 'seepgaon',
  env: ENV_STORM_NIGHT,
  heightAt,
  build(b) {
    const lambert = (color) => new THREE.MeshLambertMaterial({ color, flatShading: true });
    const basic = (color, extra = {}) => new THREE.MeshBasicMaterial({ color, ...extra });

    // ---- wet ground: sand, grass, rock, and a darker muddy lane ---------------
    const sand = new THREE.Color(0xa8966f), grass = new THREE.Color(0x587f52), rock = new THREE.Color(0x848a92);
    const mud = new THREE.Color(0x7d6a50), wet = new THREE.Color(0x6f6650);
    b.terrain({ colorAt(h, x, z, c) {
      if (h < 0.3) c.copy(wet);
      else if (h < 1.1) c.copy(wet).lerp(sand, smoothstep(0.3, 0.8, h));
      else if (h < 6.5) c.copy(sand).lerp(grass, smoothstep(1.1, 1.5, h));
      else c.copy(grass).lerp(rock, smoothstep(6.5, 9, h));
      let d = 99;
      for (let i = 0; i < LANE.length - 1; i++) d = Math.min(d, distSegPoint(LANE[i][0], LANE[i][1], LANE[i + 1][0], LANE[i + 1][1], x, z));
      c.lerp(mud, 1 - smoothstep(1.2, 3, d));
    } });
    // Puddles on the lane.
    const puddles = [[-3, 33, 1.5], [-1.5, 17, 1.2], [5.5, 4, 1.7], [4, -14, 1.3], [0.5, -26, 1.6], [-8, 26, 1.1], [9, 22, 1.2]];
    b.instanced(new THREE.CircleGeometry(1, 12).rotateX(-Math.PI / 2),
      basic(0x3a4b5f, { transparent: true, opacity: 0.55, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1 }),
      puddles, ([x, z, r], d) => { d.position.set(x, heightAt(x, z) + 0.06, z); d.scale.set(r, 1, r * 0.7); }, false);

    // ---- lighthouse yard ---------------------------------------------------
    // Stone walls: [x, z, sizeX, sizeZ, height]. Gate on the south side, a broken gap in the west wall.
    b.boxes(0x9a9588, [
      [0, -52, 20.8, 0.8, 2.2], [10, -42, 0.8, 20, 2.2],
      [-10, -48, 0.8, 8, 2.2], [-10, -37, 0.8, 9.2, 2.2],
      [-6.2, -32, 8.4, 0.8, 2.2], [6.2, -32, 8.4, 0.8, 2.2],
      // loose stone walls in the village: good hiding spots
      [-12, 30, 0.8, 6, 2], [14, -12, 5, 0.8, 2], [-6, -13.5, 0.8, 4, 2], [16, 8, 0.8, 5, 2],
    ]);

    const tower = new THREE.Group();
    const stone = lambert(0xd8d4c8);
    const shaft = new THREE.Mesh(new THREE.CylinderGeometry(2.3, 3, TOWER_H, 12), stone);
    shaft.position.y = TOWER_H / 2;
    const band = new THREE.Mesh(new THREE.CylinderGeometry(2.62, 2.74, 2.4, 12), lambert(0x8f3a2e));
    band.position.y = TOWER_H * 0.55;
    const gallery = new THREE.Mesh(new THREE.CylinderGeometry(3.2, 3.2, 0.3, 12), lambert(0x6f6a60));
    gallery.position.y = TOWER_H;
    const lampMat = basic(0xfff1c9, { fog: false });
    const lamp = new THREE.Mesh(new THREE.CylinderGeometry(1.5, 1.5, 2.4, 10), lampMat);
    lamp.position.y = TOWER_H + 1.35;
    const cap = new THREE.Mesh(new THREE.ConeGeometry(2.1, 1.6, 10), lambert(0x7a2f25));
    cap.position.y = TOWER_H + 3.35;
    const door = new THREE.Mesh(new THREE.BoxGeometry(1.4, 2.3, 0.3), lambert(0x3a2a1c));
    door.position.set(0, 1.15, 2.9);
    // Rotating beam: two long see-through cones.
    const beam = new THREE.Group();
    const beamMat = basic(0xfff1c9, { transparent: true, opacity: 0.2, blending: THREE.AdditiveBlending, depthWrite: false, fog: false, side: THREE.DoubleSide });
    for (const dir of [1, -1]) {
      const cone = new THREE.Mesh(new THREE.ConeGeometry(7, 90, 12, 1, true), beamMat);
      cone.rotation.z = dir * Math.PI / 2;
      cone.position.x = dir * 45;
      beam.add(cone);
    }
    beam.position.y = TOWER_H + 1.35;
    // Soft halo so the lit lamp reads from the far end of the village.
    const halo = new THREE.Mesh(new THREE.SphereGeometry(4.5, 12, 8),
      basic(0xffe2a0, { transparent: true, opacity: 0.3, blending: THREE.AdditiveBlending, depthWrite: false, fog: false }));
    halo.position.y = TOWER_H + 1.35;
    tower.add(shaft, band, gallery, lamp, cap, door, beam, halo);
    tower.position.set(YARD.x, PLATEAU, YARD.z);
    tower.traverse((o) => { if (o.isMesh && o.material !== beamMat && o.material !== lampMat && o !== halo) o.castShadow = true; });
    b.add(tower);
    b.collider(YARD.x, YARD.z, 5.4, 5.4, TOWER_H, true);

    // The men in black on the gallery (shown only in the cutscene) + sparks from the cut wires.
    const cutters = new THREE.Group();
    const black = lambert(0x14161b);
    for (const [x, z] of [[2.1, 1.4], [-1.7, 1.9]]) {
      const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.3, 0.75, 4, 8), black);
      body.position.set(x, 1.1, z);
      const head = new THREE.Mesh(new THREE.SphereGeometry(0.21, 8, 6), black);
      head.position.set(x, 1.82, z);
      cutters.add(body, head);
    }
    const spark = new THREE.Mesh(new THREE.SphereGeometry(0.34, 6, 5), basic(0xcfe6ff, { fog: false }));
    spark.position.set(0.4, 1.0, 1.6);
    cutters.add(spark);
    cutters.position.set(YARD.x, PLATEAU + TOWER_H, YARD.z);
    cutters.visible = false;
    b.add(cutters);

    // ---- village -------------------------------------------------------------
    // Houses: [x, z, sizeX, sizeZ, height, litWindow]
    const houses = [
      [-8, -22, 6, 5, 3.2, 1], [9, -21, 6, 5, 3.2, 0], [-3, -6, 5, 6, 3.2, 1], [15, -4, 6, 6, 3.4, 0],
      [-13, -8, 5, 5, 3, 0], [13, 18, 6, 5, 3.2, 1], [-20, 10, 5, 6, 3, 0], [3, 27, 6, 5, 3.2, 0],
      [-10, 40, 6, 5, 3.2, 1],  // Veer's home
      [5, 41, 5, 5, 3, 0],
    ];
    b.boxes(0xb9a98c, houses);
    b.instanced(new THREE.ConeGeometry(1, 1, 4).rotateY(Math.PI / 4), 0x8a4532, houses, ([x, z, sx, sz, h], d) => {
      d.position.set(x, heightAt(x, z) + h + 0.9, z);
      d.scale.set(sx * 0.82, 1.8, sz * 0.82);
    });
    b.instanced(new THREE.PlaneGeometry(0.9, 0.9), basic(0xffc56b), houses.filter((h) => h[5]), ([x, z, , sz], d) => {
      d.position.set(x + 1.2, heightAt(x, z) + 1.7, z + sz / 2 + 0.03);
    }, false);
    // Boat shed: darker wood. Dadaji's tin box sits at its front.
    b.boxes(0x6d5a44, [[-10, 18, 6, 5, 2.8]]);
    b.instanced(new THREE.ConeGeometry(1, 1, 4).rotateY(Math.PI / 4), 0x4f4034, [[-10, 18]], ([x, z], d) => {
      d.position.set(x, heightAt(x, z) + 2.8 + 0.6, z); d.scale.set(5.2, 1.2, 4.4);
    });

    // Tall hiding spots (block sight): crate stacks and net-drying racks.
    b.boxes(0x7a5a3a, [[7.5, -34.2, 1.2, 1.2, 2.2], [-7.5, -49.5, 1.2, 1.2, 2.2], [4, -18, 1.2, 1.2, 2.2], [-1, 2, 1.2, 1.2, 2.2],
      [8, 13, 1.2, 1.2, 2.2], [-6.5, 29, 1.2, 1.2, 2.2], [-15, 22, 1.2, 1.2, 2.2]]);
    b.boxes(0x3f4a44, [[9.5, 5, 4, 0.5, 2.2], [-5, 10, 0.5, 4, 2.2]]);
    // Low props (block movement, not sight): the well, barrels, an upturned boat.
    b.boxes(0x8a8a86, [[3, 8, 1.8, 1.8, 1]]);
    const barrels = [[-2, -30], [11, -16], [1.5, -2], [12, 12], [-15, 37], [7, 35.5], [-13.5, 24]];
    b.instanced(new THREE.CylinderGeometry(0.45, 0.45, 1.1, 8), 0x6b4a2f, barrels, ([x, z], d) => {
      const col = b.collider(x, z, 0.9, 0.9, 1.1, false);
      d.position.set(x, col.y + 0.5, z);
    });
    b.boxes(0x2f5a6f, [[-16, 30, 1.6, 4, 0.9]]);

    // Palms bending in the wind.
    const palms = [[-22, -2], [22, 6], [-18, 34], [14, 30], [24, -16], [-24, -24], [-2, 50], [16, 44], [-26, 20], [20, 22]];
    b.instanced(new THREE.CylinderGeometry(0.16, 0.28, 1, 6), 0x6a5238, palms, ([x, z], d) => {
      const col = b.collider(x, z, 0.6, 0.6, 5, false);
      d.position.set(x, col.y + 2.4, z); d.scale.set(1, 5.2, 1); d.rotation.z = -0.12;
    });
    b.instanced(new THREE.ConeGeometry(2.3, 1.3, 6), 0x2f6a45, palms, ([x, z], d) => {
      d.position.set(x + 0.6, heightAt(x, z) + 5.2, z); d.rotation.z = -0.3;
    });

    // Street lamps: a post, a bulb and a lit circle on the ground. Standing in the circle = exposed.
    const lamps = [[0.5, -25.5], [7.5, -2.5], [1, 16], [-2, 33]];
    b.instanced(new THREE.CylinderGeometry(0.07, 0.09, 3.2, 6), 0x2c2c2c, lamps, ([x, z], d) => { d.position.set(x, heightAt(x, z) + 1.6, z); });
    b.instanced(new THREE.SphereGeometry(0.22, 8, 6), basic(0xffd27a, { fog: false }), lamps, ([x, z], d) => { d.position.set(x, heightAt(x, z) + 3.3, z); }, false);
    for (const [x, z] of lamps) b.groundGlow(x, z, 6, 0xffb860, 0.32);

    // Dadaji's tin box (hidden until the mission shows it).
    const tinBox = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.35, 0.4), lambert(0xb8893a));
    tinBox.position.set(SEEPGAON.shed.x, heightAt(SEEPGAON.shed.x, SEEPGAON.shed.z) + 0.2, SEEPGAON.shed.z - 1.3);
    tinBox.visible = false;
    b.add(tinBox);

    // Far away: the island (a black shape against the sky, clearest in lightning) and Baba's boat lamp.
    const island = new THREE.Group();
    const dark = basic(0x04070b, { fog: false });
    for (const [dx, dz, r, h] of [[0, 0, 60, 46], [-55, 20, 45, 28], [50, -15, 40, 22]]) {
      const peak = new THREE.Mesh(new THREE.ConeGeometry(r, h, 7), dark);
      peak.position.set(dx, h / 2 - 2, dz);
      island.add(peak);
    }
    island.position.set(SEEPGAON.island.x, 0, SEEPGAON.island.z);
    b.add(island);
    const boatLamp = new THREE.Mesh(new THREE.SphereGeometry(0.7, 6, 5), basic(0xffb860, { fog: false }));
    boatLamp.position.set(70, 2, 190);
    b.add(boatLamp);

    // ---- handles for missions --------------------------------------------------
    let lit = true, flickerT = -1;
    const lighthouse = {
      get lit() { return lit; },
      setLit(v) {
        lit = v; flickerT = -1;
        lampMat.color.setHex(v ? 0xfff1c9 : 0x161c24);
        beam.visible = halo.visible = v;
      },
      // Flickers three times, then stays dark.
      flickerOut() { flickerT = 0; },
    };
    return {
      lighthouse, cutters, tinBox,
      update(dt, time) {
        beam.rotation.y += dt * 0.5;
        boatLamp.position.y = 1.6 + Math.sin(time * 1.3) * 1.4;
        boatLamp.visible = Math.sin(time * 0.9) > -0.6; // lost behind the waves now and then
        if (cutters.visible) spark.visible = Math.sin(time * 37) * Math.sin(time * 11) > 0.2;
        if (flickerT >= 0) {
          flickerT += dt;
          const on = flickerT < 2.4 && Math.floor(flickerT / 0.4) % 2 === 1; // off-on x3
          lampMat.color.setHex(on ? 0xfff1c9 : 0x161c24);
          beam.visible = halo.visible = on;
          if (flickerT >= 2.4) lighthouse.setLit(false);
        }
      },
    };
  },
};
