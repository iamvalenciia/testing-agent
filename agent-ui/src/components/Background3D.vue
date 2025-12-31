<template>
  <div ref="canvasContainer" class="three-bg"></div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref, watch } from 'vue';
import * as THREE from 'three';

const props = defineProps({
  isDark: {
    type: Boolean,
    default: true
  }
});

const canvasContainer = ref(null);
let scene, camera, renderer, particles, lines, animationId;
let mouseX = 0, mouseY = 0;

function getColors(isDark) {
  return {
    background: isDark ? 0x0a0a0a : 0xf5f5f5,
    particles: isDark ? 0xffffff : 0x1a1a1a,
    lines: isDark ? 0x333333 : 0xcccccc,
    particleOpacity: isDark ? 0.5 : 0.6,
    lineOpacity: isDark ? 0.1 : 0.15
  };
}

function updateColors() {
  const colors = getColors(props.isDark);
  if (scene) scene.background = new THREE.Color(colors.background);
  if (particles) {
    particles.material.color.setHex(colors.particles);
    particles.material.opacity = colors.particleOpacity;
  }
  if (lines) {
    lines.material.color.setHex(colors.lines);
    lines.material.opacity = colors.lineOpacity;
  }
}

watch(() => props.isDark, updateColors);

onMounted(() => {
  const colors = getColors(props.isDark);
  
  scene = new THREE.Scene();
  scene.background = new THREE.Color(colors.background);
  
  camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
  camera.position.z = 100;

  // Using WebGLRenderer with powerPreference for best GPU performance
  renderer = new THREE.WebGLRenderer({ 
    antialias: true, 
    alpha: true,
    powerPreference: 'high-performance'  // WebGL GPU acceleration
  });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  canvasContainer.value.appendChild(renderer.domElement);

  // Create Particles
  const geometry = new THREE.BufferGeometry();
  const count = 400;
  const positions = new Float32Array(count * 3);
  
  for(let i = 0; i < count * 3; i++) {
    positions[i] = (Math.random() - 0.5) * 250;
  }
  
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  
  const material = new THREE.PointsMaterial({ 
    size: 0.6, 
    color: colors.particles,
    transparent: true,
    opacity: colors.particleOpacity,
    sizeAttenuation: true
  });

  particles = new THREE.Points(geometry, material);
  scene.add(particles);

  // Connecting lines
  const lineGeometry = new THREE.BufferGeometry();
  const linePositions = new Float32Array(80 * 6);
  for (let i = 0; i < 80; i++) {
    const idx = i * 6;
    linePositions[idx] = (Math.random() - 0.5) * 180;
    linePositions[idx + 1] = (Math.random() - 0.5) * 180;
    linePositions[idx + 2] = (Math.random() - 0.5) * 180;
    linePositions[idx + 3] = (Math.random() - 0.5) * 180;
    linePositions[idx + 4] = (Math.random() - 0.5) * 180;
    linePositions[idx + 5] = (Math.random() - 0.5) * 180;
  }
  lineGeometry.setAttribute('position', new THREE.BufferAttribute(linePositions, 3));
  const lineMaterial = new THREE.LineBasicMaterial({ 
    color: colors.lines,
    transparent: true, 
    opacity: colors.lineOpacity
  });
  lines = new THREE.LineSegments(lineGeometry, lineMaterial);
  scene.add(lines);

  // Animation loop - optimized for 60fps
  let lastTime = 0;
  const targetFPS = 60;
  const frameInterval = 1000 / targetFPS;

  const animate = (currentTime) => {
    animationId = requestAnimationFrame(animate);
    
    // Frame rate limiting for consistent performance
    const delta = currentTime - lastTime;
    if (delta < frameInterval) return;
    lastTime = currentTime - (delta % frameInterval);
    
    // Smooth rotation
    particles.rotation.x += 0.0002;
    particles.rotation.y += 0.0003;
    lines.rotation.x += 0.00015;
    lines.rotation.y += 0.00025;

    // Mouse interaction (subtle)
    camera.position.x += (mouseX * 0.03 - camera.position.x) * 0.01;
    camera.position.y += (-mouseY * 0.03 - camera.position.y) * 0.01;
    camera.lookAt(scene.position);

    // Breathing effect
    const time = currentTime * 0.0003;
    particles.scale.setScalar(1 + Math.sin(time) * 0.03);

    renderer.render(scene, camera);
  };
  
  animate(0);

  window.addEventListener('resize', onWindowResize);
  window.addEventListener('mousemove', onMouseMove);
});

const onWindowResize = () => {
  if (!camera || !renderer) return;
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
};

const onMouseMove = (event) => {
  mouseX = (event.clientX - window.innerWidth / 2);
  mouseY = (event.clientY - window.innerHeight / 2);
};

onBeforeUnmount(() => {
  cancelAnimationFrame(animationId);
  window.removeEventListener('resize', onWindowResize);
  window.removeEventListener('mousemove', onMouseMove);
  if (renderer) {
    renderer.dispose();
  }
});
</script>

<style scoped>
.three-bg {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
  pointer-events: none;
}
</style>
