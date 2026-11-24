precision highp float;
varying vec2 v_coords;
uniform vec2 size;
uniform vec2 u_camera;

// Rounded light falloff along a square lattice. A second, broad wave
// reveals short runs of edges as the camera crosses each layer.
float lattice(vec2 screen, float pitch, float depth, vec2 offset) {
    vec2 p = screen + mod(u_camera * depth, pitch * 12.0) + offset;
    vec2 edge = abs(fract(p / pitch + 0.5) - 0.5) * pitch;
    float d = min(edge.x, edge.y);
    float phase = 6.2831853 / (12.0 * pitch);
    float wave = sin(p.x * phase + p.y * phase * 2.0)
               + cos(p.y * phase - p.x * phase * 3.0);
    return smoothstep(-0.85, 1.15, wave)
         * (0.7 * exp(-d * 1.4) + 0.17 * exp(-d * 0.20));
}

void main() {
    vec2 p = v_coords * size;
    vec3 color = vec3(0.018, 0.032, 0.095);
    color += vec3(0.045, 0.12, 0.27) * lattice(p, 32.0, 0.15, vec2(8.0));
    color += vec3(0.03, 0.84, 0.99) * lattice(p, 104.0, 0.42, vec2(15.0, 4.0));
    color += vec3(0.94, 0.09, 0.68) * lattice(p, 144.0, 0.76, vec2(62.0, 39.0));
    gl_FragColor = vec4(color, 1.0);
}
