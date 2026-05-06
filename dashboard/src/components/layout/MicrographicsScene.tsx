"use client";

import { useRef, useMemo } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { EffectComposer, Bloom, ChromaticAberration, Vignette } from "@react-three/postprocessing";
import { BlendFunction } from "postprocessing";
import * as THREE from "three";

function seededUnit(seed: number) {
  const value = Math.sin(seed * 12.9898) * 43758.5453;
  return value - Math.floor(value);
}

/* ─── Emissive Ring ──────────────────────────────────────── */

function GlowRing({
  radius,
  value,
  color,
  speed,
  thickness = 0.03,
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

  useFrame((state) => {
    if (ref.current) {
      ref.current.rotation.z += speed * 0.008;
    }
  });

  // Full ring — emissive material makes it glow through bloom
  return (
    <mesh ref={ref} position={[0, y, 0]} rotation={[Math.PI / 2, 0, 0]}>
      <torusGeometry args={[radius, thickness, 16, 128]} />
      <meshBasicMaterial
        color={color}
        transparent
        opacity={0.7 + value * 0.3}
        toneMapped={false}
      />
    </mesh>
  );
}

/* ─── Arc Segment (partial ring showing value) ───────────── */

function ArcSegment({
  radius,
  value,
  color,
  thickness = 0.05,
  y = 0,
}: {
  radius: number;
  value: number;
  color: string;
  thickness?: number;
  y?: number;
}) {
  const geo = useMemo(() => {
    const arc = Math.max(0.01, value) * Math.PI * 2;
    return new THREE.TorusGeometry(radius, thickness, 8, 64, arc);
  }, [radius, thickness, value]);

  return (
    <mesh position={[0, y, 0]} rotation={[Math.PI / 2, -Math.PI / 2, 0]} geometry={geo}>
      <meshBasicMaterial color={color} toneMapped={false} />
    </mesh>
  );
}

/* ─── Sweep Line ─────────────────────────────────────────── */

function SweepLine({ radius, speed, color }: { radius: number; speed: number; color: string }) {
  const ref = useRef<THREE.Group>(null);

  useFrame((state) => {
    if (ref.current) {
      ref.current.rotation.z = state.clock.elapsedTime * speed;
    }
  });

  const points = useMemo(() => [new THREE.Vector3(0, 0, 0), new THREE.Vector3(radius, 0, 0)], [radius]);
  const lineGeo = useMemo(() => new THREE.BufferGeometry().setFromPoints(points), [points]);

  return (
    <group ref={ref} rotation={[Math.PI / 2, 0, 0]}>
      <primitive object={new THREE.Line(lineGeo, new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.9, toneMapped: false }))} />
    </group>
  );
}

/* ─── Grid Lines (crosshairs) ────────────────────────────── */

function GridLines({ size, color }: { size: number; color: string }) {
  const points = useMemo(() => {
    const arr: THREE.Vector3[] = [];
    // Horizontal
    arr.push(new THREE.Vector3(-size, 0, 0), new THREE.Vector3(size, 0, 0));
    // Vertical
    arr.push(new THREE.Vector3(0, -size, 0), new THREE.Vector3(0, size, 0));
    // Diagonals
    const d = size * 0.7;
    arr.push(new THREE.Vector3(-d, -d, 0), new THREE.Vector3(d, d, 0));
    arr.push(new THREE.Vector3(d, -d, 0), new THREE.Vector3(-d, d, 0));
    return arr;
  }, [size]);

  const geo = useMemo(() => new THREE.BufferGeometry().setFromPoints(points), [points]);

  return (
    <lineSegments geometry={geo} rotation={[Math.PI / 2, 0, 0]}>
      <lineBasicMaterial color={color} transparent opacity={0.12} toneMapped={false} />
    </lineSegments>
  );
}

/* ─── Waveform Line ──────────────────────────────────────── */

function WaveformLine({
  data,
  color,
  width = 3,
  y = 0,
  amplitude = 0.4,
}: {
  data: number[];
  color: string;
  width?: number;
  y?: number;
  amplitude?: number;
}) {
  const ref = useRef<THREE.Line>(null);

  useFrame((state) => {
    if (!ref.current) return;
    const geo = ref.current.geometry;
    const positions = geo.attributes.position;
    const t = state.clock.elapsedTime;

    for (let i = 0; i < data.length; i++) {
      const x = (i / (data.length - 1)) * width - width / 2;
      const val = data[i] ?? 0.5;
      const jitter = Math.sin(t * 2.5 + i * 0.6) * 0.008;
      positions.setXYZ(i, x, (val - 0.5) * amplitude + jitter, 0);
    }
    positions.needsUpdate = true;
  });

  const geo = useMemo(() => {
    const pts = data.map((v, i) => {
      const x = (i / (data.length - 1)) * width - width / 2;
      return new THREE.Vector3(x, (v - 0.5) * amplitude, 0);
    });
    return new THREE.BufferGeometry().setFromPoints(pts);
  }, [data, width, amplitude]);

  return (
    <primitive object={new THREE.Line(geo, new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.9, toneMapped: false }))} ref={ref} position={[0, y, 0]} />
  );
}

/* ─── Floating Particles ─────────────────────────────────── */

function Particles({ count, color, spread }: { count: number; color: string; spread: number }) {
  const ref = useRef<THREE.Points>(null);

  const positions = useMemo(() => {
    const arr = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      arr[i * 3] = (seededUnit(i * 3 + 1) - 0.5) * spread;
      arr[i * 3 + 1] = (seededUnit(i * 3 + 2) - 0.5) * spread * 0.6;
      arr[i * 3 + 2] = (seededUnit(i * 3 + 3) - 0.5) * spread * 0.2 - 0.5;
    }
    return arr;
  }, [count, spread]);

  useFrame((state) => {
    if (ref.current) {
      ref.current.rotation.y = state.clock.elapsedTime * 0.015;
    }
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        color={color}
        size={0.015}
        transparent
        opacity={0.6}
        sizeAttenuation
        toneMapped={false}
      />
    </points>
  );
}

/* ─── Agent Blips ────────────────────────────────────────── */

function Blips({
  blips,
  color,
  radius,
}: {
  blips: { angle: number; dist: number; intensity: number }[];
  color: string;
  radius: number;
}) {
  return (
    <group rotation={[Math.PI / 2, 0, 0]}>
      {blips.map((b, i) => {
        const x = Math.cos(b.angle) * b.dist * radius;
        const y = Math.sin(b.angle) * b.dist * radius;
        return (
          <mesh key={i} position={[x, y, 0]}>
            <sphereGeometry args={[0.015 + b.intensity * 0.01, 8, 8]} />
            <meshBasicMaterial
              color={color}
              transparent
              opacity={0.3 + b.intensity * 0.7}
              toneMapped={false}
            />
          </mesh>
        );
      })}
    </group>
  );
}

/* ─── Tick Marks ─────────────────────────────────────────── */

function TickRing({ radius, color, count = 72 }: { radius: number; color: string; count?: number }) {
  const positions = useMemo(() => {
    const arr: number[] = [];
    for (let i = 0; i < count; i++) {
      const angle = (i / count) * Math.PI * 2;
      const major = i % 6 === 0;
      const inner = radius - (major ? 0.05 : 0.025);
      arr.push(
        Math.cos(angle) * inner, Math.sin(angle) * inner, 0,
        Math.cos(angle) * radius, Math.sin(angle) * radius, 0,
      );
    }
    return new Float32Array(arr);
  }, [radius, count]);

  return (
    <lineSegments rotation={[Math.PI / 2, 0, 0]}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <lineBasicMaterial color={color} transparent opacity={0.35} toneMapped={false} />
    </lineSegments>
  );
}

/* ─── Scene ──────────────────────────────────────────────── */

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

function Scene(props: SceneProps) {
  const groupRef = useRef<THREE.Group>(null);

  useFrame((state) => {
    if (groupRef.current) {
      groupRef.current.rotation.y = Math.sin(state.clock.elapsedTime * 0.12) * 0.04;
      groupRef.current.rotation.x = 0.15 + Math.sin(state.clock.elapsedTime * 0.08) * 0.02;
    }
  });

  const sweepSpeed = 0.4 + (props.agentCount / 30) * 0.6;

  return (
    <>
      <Particles count={200 + Math.floor(props.stigmergyDensity / 8)} color="#4FD1D9" spread={5} />

      <group ref={groupRef}>
        {/* Grid crosshairs */}
        <GridLines size={1.4} color="#4FD1D9" />

        {/* Outer ring: fitness (cyan) */}
        <GlowRing radius={1.2} value={props.fitness} color="#4FD1D9" speed={0.3} thickness={0.015} />
        <ArcSegment radius={1.2} value={props.fitness} color="#4FD1D9" thickness={0.035} />
        <TickRing radius={1.25} color="#4FD1D9" count={72} />

        {/* Second ring: tasks (green) */}
        <GlowRing radius={1.0} value={props.taskCompletion} color="#8FA89B" speed={-0.4} thickness={0.012} />
        <ArcSegment radius={1.0} value={props.taskCompletion} color="#8FA89B" thickness={0.03} />
        <TickRing radius={1.04} color="#8FA89B" count={36} />

        {/* Third ring: health (gold) */}
        <GlowRing radius={0.8} value={props.healthScore} color="#D4A855" speed={0.5} thickness={0.01} />
        <ArcSegment radius={0.8} value={props.healthScore} color="#D4A855" thickness={0.025} />

        {/* Inner ring: evolution (pink) */}
        <GlowRing radius={0.6} value={Math.min(1, props.evolutionEntries / 150)} color="#D47DB5" speed={-0.7} thickness={0.008} />
        <ArcSegment radius={0.6} value={Math.min(1, props.evolutionEntries / 150)} color="#D47DB5" thickness={0.02} />

        {/* Sweep line */}
        <SweepLine radius={0.55} speed={sweepSpeed} color="#4FD1D9" />

        {/* Agent blips */}
        <Blips blips={props.agentBlips} color="#00ffcc" radius={0.5} />

        {/* Waveform: fitness trend */}
        <WaveformLine data={props.fitnessTrend} color="#4FD1D9" width={2.6} y={-0.75} amplitude={0.35} />

        {/* Second waveform: inverted, pink */}
        <WaveformLine
          data={props.fitnessTrend.map((v) => 1 - v)}
          color="#D47DB5"
          width={2.6}
          y={-0.85}
          amplitude={0.2}
        />

        {/* Third waveform: health rhythm */}
        <WaveformLine
          data={props.fitnessTrend.map((v, i) => 0.5 + Math.sin(i * 0.3) * 0.3 * v)}
          color="#D4A855"
          width={2.6}
          y={-0.95}
          amplitude={0.15}
        />
      </group>

      {/* Heavy bloom for glow */}
      <EffectComposer>
        <Bloom
          intensity={2.5}
          luminanceThreshold={0.05}
          luminanceSmoothing={0.4}
          mipmapBlur
        />
        <ChromaticAberration
          blendFunction={BlendFunction.NORMAL}
          offset={new THREE.Vector2(0.001, 0.001)}
        />
        <Vignette eskil={false} offset={0.1} darkness={0.8} />
      </EffectComposer>
    </>
  );
}

/* ─── Export ──────────────────────────────────────────────── */

export function MicrographicsScene(props: SceneProps) {
  return (
    <div
      className="relative overflow-hidden rounded-xl"
      style={{
        height: 300,
        background: "#000810",
      }}
    >
      <Canvas
        camera={{ position: [0, 0.6, 2.8], fov: 55 }}
        dpr={[1, 2]}
        gl={{
          antialias: true,
          alpha: false,
          powerPreference: "high-performance",
          toneMapping: THREE.NoToneMapping,
        }}
        onCreated={({ gl }) => {
          gl.setClearColor("#000810");
        }}
      >
        <Scene {...props} />
      </Canvas>

      {/* CRT scanlines */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background: "repeating-linear-gradient(transparent, transparent 1px, rgba(0,0,0,0.08) 1px, rgba(0,0,0,0.08) 2px)",
          mixBlendMode: "multiply",
        }}
      />
    </div>
  );
}
