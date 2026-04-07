"use client";

import { useRef, useMemo, useCallback } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { EffectComposer, Bloom, ChromaticAberration, Scanline } from "@react-three/postprocessing";
import { BlendFunction } from "postprocessing";
import * as THREE from "three";

/* ─── Hologram Ring Gauge ────────────────────────────────── */

function HoloRing({
  radius,
  value,
  color,
  speed,
  thickness = 0.04,
  y = 0,
}: {
  radius: number;
  value: number;
  color: string;
  speed: number;
  thickness?: number;
  y?: number;
}) {
  const ref = useRef<THREE.Mesh>(null);
  const materialRef = useRef<THREE.ShaderMaterial>(null);

  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uValue: { value: value },
      uColor: { value: new THREE.Color(color) },
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  useFrame((state) => {
    if (ref.current) {
      ref.current.rotation.y += speed * 0.01;
      ref.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.3) * 0.05;
    }
    if (materialRef.current) {
      materialRef.current.uniforms.uTime.value = state.clock.elapsedTime;
      materialRef.current.uniforms.uValue.value +=
        (value - materialRef.current.uniforms.uValue.value) * 0.05;
    }
  });

  return (
    <mesh ref={ref} position={[0, y, 0]} rotation={[Math.PI / 2, 0, 0]}>
      <torusGeometry args={[radius, thickness, 16, 128]} />
      <shaderMaterial
        ref={materialRef}
        transparent
        depthWrite={false}
        blending={THREE.AdditiveBlending}
        uniforms={uniforms}
        vertexShader={`
          varying vec2 vUv;
          void main() {
            vUv = uv;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
          }
        `}
        fragmentShader={`
          uniform float uTime;
          uniform float uValue;
          uniform vec3 uColor;
          varying vec2 vUv;

          void main() {
            // Arc fill based on value (0-1)
            float angle = vUv.x;
            float fill = step(angle, uValue);

            // Pulse effect
            float pulse = 0.7 + 0.3 * sin(uTime * 2.0 + angle * 6.28);

            // Edge glow
            float edge = 1.0 - abs(vUv.y - 0.5) * 2.0;
            edge = pow(edge, 0.5);

            float alpha = fill * pulse * edge * 0.85;
            vec3 finalColor = uColor * (1.0 + pulse * 0.3);

            gl_FragColor = vec4(finalColor, alpha);
          }
        `}
      />
    </mesh>
  );
}

/* ─── Sweep Radar ────────────────────────────────────────── */

function SweepRadar({
  radius,
  speed,
  color,
  blips,
}: {
  radius: number;
  speed: number;
  color: string;
  blips: { angle: number; dist: number; intensity: number }[];
}) {
  const sweepRef = useRef<THREE.Mesh>(null);
  const materialRef = useRef<THREE.ShaderMaterial>(null);

  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uColor: { value: new THREE.Color(color) },
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  );

  useFrame((state) => {
    if (sweepRef.current) {
      sweepRef.current.rotation.z = state.clock.elapsedTime * speed;
    }
    if (materialRef.current) {
      materialRef.current.uniforms.uTime.value = state.clock.elapsedTime;
    }
  });

  return (
    <group position={[0, 0, -0.1]}>
      {/* Grid rings */}
      {[0.25, 0.5, 0.75, 1.0].map((pct) => (
        <mesh key={pct} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[radius * pct, 0.005, 8, 64]} />
          <meshBasicMaterial color={color} transparent opacity={0.1} blending={THREE.AdditiveBlending} />
        </mesh>
      ))}

      {/* Sweep cone */}
      <mesh ref={sweepRef} rotation={[Math.PI / 2, 0, 0]}>
        <circleGeometry args={[radius, 32, 0, Math.PI * 0.4]} />
        <shaderMaterial
          ref={materialRef}
          transparent
          depthWrite={false}
          side={THREE.DoubleSide}
          blending={THREE.AdditiveBlending}
          uniforms={uniforms}
          vertexShader={`
            varying vec2 vUv;
            void main() {
              vUv = uv;
              gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
            }
          `}
          fragmentShader={`
            uniform float uTime;
            uniform vec3 uColor;
            varying vec2 vUv;
            void main() {
              float dist = length(vUv - vec2(0.0, 0.5));
              float fade = 1.0 - vUv.x;
              float alpha = fade * 0.25 * (1.0 - dist * 0.8);
              gl_FragColor = vec4(uColor, alpha);
            }
          `}
        />
      </mesh>

      {/* Blips */}
      {blips.map((blip, i) => {
        const x = Math.cos(blip.angle) * blip.dist * radius;
        const z = Math.sin(blip.angle) * blip.dist * radius;
        return (
          <mesh key={i} position={[x, 0, z]}>
            <sphereGeometry args={[0.02, 8, 8]} />
            <meshBasicMaterial
              color={color}
              transparent
              opacity={blip.intensity}
              blending={THREE.AdditiveBlending}
            />
          </mesh>
        );
      })}
    </group>
  );
}

/* ─── Waveform (3D ribbon) ───────────────────────────────── */

function Waveform3D({
  data,
  color,
  width = 3,
  height = 0.8,
  y = 0,
}: {
  data: number[];
  color: string;
  width?: number;
  height?: number;
  y?: number;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const geoRef = useRef<THREE.BufferGeometry>(null);

  useFrame((state) => {
    if (!geoRef.current || data.length < 2) return;
    const positions = geoRef.current.attributes.position;
    const count = data.length;

    for (let i = 0; i < count; i++) {
      const x = (i / (count - 1)) * width - width / 2;
      const val = data[i] ?? 0.5;
      const jitter = Math.sin(state.clock.elapsedTime * 3 + i * 0.5) * 0.01;
      const yVal = (val - 0.5) * height + jitter;

      // Top vertex
      positions.setXYZ(i * 2, x, yVal + 0.015, 0);
      // Bottom vertex
      positions.setXYZ(i * 2 + 1, x, yVal - 0.015, 0);
    }
    positions.needsUpdate = true;
  });

  const geometry = useMemo(() => {
    const count = Math.max(data.length, 28);
    const verts = new Float32Array(count * 2 * 3);
    const indices: number[] = [];

    for (let i = 0; i < count; i++) {
      const x = (i / (count - 1)) * width - width / 2;
      verts[i * 6] = x;
      verts[i * 6 + 1] = 0;
      verts[i * 6 + 2] = 0;
      verts[i * 6 + 3] = x;
      verts[i * 6 + 4] = -0.03;
      verts[i * 6 + 5] = 0;

      if (i < count - 1) {
        const a = i * 2;
        indices.push(a, a + 1, a + 2, a + 1, a + 3, a + 2);
      }
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(verts, 3));
    geo.setIndex(indices);
    return geo;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data.length, width]);

  return (
    <mesh ref={meshRef} position={[0, y, 0]} geometry={geometry}>
      <bufferGeometry ref={geoRef} attach="geometry" {...geometry} />
      <meshBasicMaterial
        color={color}
        transparent
        opacity={0.9}
        blending={THREE.AdditiveBlending}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}

/* ─── Particle Field ─────────────────────────────────────── */

function ParticleField({ count, color, spread }: { count: number; color: string; spread: number }) {
  const ref = useRef<THREE.Points>(null);

  const positions = useMemo(() => {
    const arr = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      arr[i * 3] = (Math.random() - 0.5) * spread;
      arr[i * 3 + 1] = (Math.random() - 0.5) * spread;
      arr[i * 3 + 2] = (Math.random() - 0.5) * spread * 0.3;
    }
    return arr;
  }, [count, spread]);

  useFrame((state) => {
    if (ref.current) {
      ref.current.rotation.y = state.clock.elapsedTime * 0.02;
      ref.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.1) * 0.05;
    }
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        color={color}
        size={0.008}
        transparent
        opacity={0.4}
        blending={THREE.AdditiveBlending}
        sizeAttenuation
      />
    </points>
  );
}

/* ─── Tick Ring (static gauge marks) ─────────────────────── */

function TickRing({ radius, color, ticks = 36 }: { radius: number; color: string; ticks?: number }) {
  const positions = useMemo(() => {
    const arr: number[] = [];
    for (let i = 0; i < ticks; i++) {
      const angle = (i / ticks) * Math.PI * 2;
      const isMajor = i % 3 === 0;
      const inner = radius - (isMajor ? 0.06 : 0.03);
      arr.push(
        Math.cos(angle) * inner, Math.sin(angle) * inner, 0,
        Math.cos(angle) * radius, Math.sin(angle) * radius, 0,
      );
    }
    return new Float32Array(arr);
  }, [radius, ticks]);

  return (
    <lineSegments rotation={[Math.PI / 2, 0, 0]}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <lineBasicMaterial color={color} transparent opacity={0.3} blending={THREE.AdditiveBlending} />
    </lineSegments>
  );
}

/* ─── Scene Composition ──────────────────────────────────── */

interface SceneProps {
  fitness: number;
  agentCount: number;
  taskCompletion: number;
  stigmergyDensity: number;
  healthScore: number;
  evolutionEntries: number;
  fitnessTrend: number[];
  agentBlips: { angle: number; dist: number; intensity: number }[];
}

function Scene({
  fitness,
  agentCount,
  taskCompletion,
  stigmergyDensity,
  healthScore,
  evolutionEntries,
  fitnessTrend,
  agentBlips,
}: SceneProps) {
  const groupRef = useRef<THREE.Group>(null);

  useFrame((state) => {
    if (groupRef.current) {
      // Subtle breathing
      groupRef.current.rotation.y = Math.sin(state.clock.elapsedTime * 0.15) * 0.03;
      groupRef.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.1) * 0.02;
    }
  });

  // Normalize values for visual parameters
  const sweepSpeed = 0.3 + (agentCount / 30) * 0.5;
  const particleCount = 100 + Math.floor(stigmergyDensity / 10);

  return (
    <>
      {/* Camera */}
      <perspectiveCamera position={[0, 0.5, 3.5]} fov={45} />

      {/* Ambient atmosphere */}
      <ParticleField count={Math.min(particleCount, 500)} color="#4FD1D9" spread={5} />

      <group ref={groupRef}>
        {/* Concentric health rings */}
        <HoloRing radius={1.2} value={fitness} color="#4FD1D9" speed={0.3} thickness={0.035} y={0} />
        <HoloRing radius={1.0} value={taskCompletion} color="#8FA89B" speed={-0.4} thickness={0.03} y={0.05} />
        <HoloRing radius={0.8} value={healthScore} color="#D4A855" speed={0.5} thickness={0.025} y={-0.05} />
        <HoloRing radius={0.6} value={Math.min(1, evolutionEntries / 150)} color="#D47DB5" speed={-0.6} thickness={0.02} y={0.02} />

        {/* Tick marks on outer ring */}
        <TickRing radius={1.25} color="#4FD1D9" ticks={72} />
        <TickRing radius={1.05} color="#8FA89B" ticks={36} />

        {/* Radar sweep in center */}
        <SweepRadar
          radius={0.5}
          speed={sweepSpeed}
          color="#4FD1D9"
          blips={agentBlips}
        />

        {/* Waveform ribbon (fitness trend) */}
        <Waveform3D
          data={fitnessTrend}
          color="#4FD1D9"
          width={2.8}
          height={0.6}
          y={-0.9}
        />

        {/* Second waveform (inverted, dimmer — creates depth) */}
        <Waveform3D
          data={fitnessTrend.map((v) => 1 - v)}
          color="#D47DB5"
          width={2.8}
          height={0.3}
          y={-1.05}
        />
      </group>

      {/* Postprocessing */}
      <EffectComposer>
        <Bloom
          intensity={1.5}
          luminanceThreshold={0.1}
          luminanceSmoothing={0.9}
          mipmapBlur
        />
        <ChromaticAberration
          blendFunction={BlendFunction.NORMAL}
          offset={new THREE.Vector2(0.0005, 0.0005)}
        />
        <Scanline blendFunction={BlendFunction.OVERLAY} density={1.2} opacity={0.08} />
      </EffectComposer>
    </>
  );
}

/* ─── Exported Component ─────────────────────────────────── */

export function MicrographicsScene(props: SceneProps) {
  return (
    <div
      className="relative overflow-hidden rounded-xl"
      style={{
        height: 280,
        background: "linear-gradient(135deg, #000810 0%, #0a0e18 100%)",
      }}
    >
      <Canvas
        camera={{ position: [0, 0.3, 3.2], fov: 50 }}
        dpr={[1, 2]}
        gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      >
        <Scene {...props} />
      </Canvas>

      {/* CRT scanline overlay */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background: "repeating-linear-gradient(transparent, transparent 1px, rgba(0,0,0,0.12) 1px, rgba(0,0,0,0.12) 2px)",
          zIndex: 10,
        }}
      />
    </div>
  );
}
