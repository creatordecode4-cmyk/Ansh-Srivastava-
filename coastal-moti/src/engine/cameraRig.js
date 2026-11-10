import * as THREE from 'three';
import { clamp, damp } from './mathx.js';

// Smooth third-person follow camera. Yaw/pitch come from mouse look or touch drag.
// yaw = 0 means the camera sits on +Z looking toward -Z.
export function createCameraRig(game) {
  const camera = game.engine.camera;
  const target = new THREE.Vector3();
  const rig = { yaw: 0, pitch: 0.32, distance: game.mobile ? 7.5 : 6.5 };
  let dist = rig.distance;
  let snapped = false;

  rig.snap = () => { snapped = false; };

  // Cutscene camera: set rig.cinematic = { from, to, look, duration } (THREE.Vector3s) and clear it after.
  rig.cinematic = null;

  rig.update = (dt, live) => {
    const c = rig.cinematic;
    if (c) {
      c.t = Math.min(1, (c.t || 0) + dt / c.duration);
      const k = c.t * c.t * (3 - 2 * c.t);
      camera.position.lerpVectors(c.from, c.to, k);
      camera.lookAt(c.look);
      game.input.lookDelta();
      snapped = false;
      return;
    }
    const p = game.player.pos;
    if (live) {
      const look = game.input.lookDelta();
      rig.yaw -= look.x;
      rig.pitch = clamp(rig.pitch + look.y, -0.15, 1.2);
    }
    const tx = p.x, ty = p.y + 1.55, tz = p.z;
    if (!snapped) { target.set(tx, ty, tz); snapped = true; }
    else target.lerp(new THREE.Vector3(tx, ty, tz), damp(14, dt));

    const cp = Math.cos(rig.pitch);
    const ox = Math.sin(rig.yaw) * cp, oy = Math.sin(rig.pitch), oz = Math.cos(rig.yaw) * cp;

    // Pull the camera in when a wall is between it and the player.
    let want = rig.distance;
    const t = game.world.segmentT(target.x, target.z, target.x + ox * want, target.z + oz * want);
    if (t <= 1) want = Math.max(1.2, want * t - 0.3);
    dist += (want - dist) * (want < dist ? 1 : damp(6, dt)); // snap in, ease out

    camera.position.set(target.x + ox * dist, target.y + oy * dist, target.z + oz * dist);
    const ground = Math.max(game.world.heightAt(camera.position.x, camera.position.z), 0) + 0.5;
    if (camera.position.y < ground) camera.position.y = ground;
    camera.lookAt(target);
  };

  // Unit vectors on the XZ plane, used for camera-relative movement and the compass.
  rig.forward = () => ({ x: -Math.sin(rig.yaw), z: -Math.cos(rig.yaw) });
  rig.right = () => ({ x: Math.cos(rig.yaw), z: -Math.sin(rig.yaw) });
  return rig;
}
