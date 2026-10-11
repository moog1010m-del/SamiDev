precision mediump float;

uniform vec2 uResolution;
uniform float uInnerRadius;
uniform float uOuterRadius;
uniform vec4 uColor0;
uniform vec4 uColor1;

void main(void) {
    // vec2 uv = (2. * gl_FragCoord.xy - uResolution.xy) / min(uResolution.x, uResolution.y);
    // Calculate the distance from the center
    // float distance = length(uv);
    // Use smoothstep to create the gradient
    // float gradient = smoothstep(uInnerRadius, uOuterRadius, distance);
    // Output the final color
    // gl_FragColor = mix(uColor0, uColor1, gradient);

    gl_FragColor = mix(uColor0, uColor1, smoothstep(uInnerRadius, uOuterRadius, length((2. * gl_FragCoord.xy - uResolution.xy) / min(uResolution.x, uResolution.y))));
}
