precision mediump float;

uniform sampler2D uTexture;
uniform float uTime;
uniform float uBlurSize;    // (.0 to infinite) The higher the less brightness
uniform float uAlpha;
varying vec2 vTextureCoord;

// From https://www.shadertoy.com/view/lsXGWn
void main(void) {
    vec4 ownColor = texture2D(uTexture, vTextureCoord);

    if (uTime == 0.) {
        gl_FragColor = ownColor;
    } else {
        if (ownColor.w < .1) discard;

        vec4 sum = vec4(0.);

        // Blur in y (vertical)
        // Take nine samples, with the distance blurSize between them
        sum += texture2D(uTexture, vec2(vTextureCoord.x - 4.*uBlurSize, vTextureCoord.y)) * .05;
        sum += texture2D(uTexture, vec2(vTextureCoord.x - 3.*uBlurSize, vTextureCoord.y)) * .09;
        sum += texture2D(uTexture, vec2(vTextureCoord.x - 2.*uBlurSize, vTextureCoord.y)) * .12;
        sum += texture2D(uTexture, vec2(vTextureCoord.x - uBlurSize, vTextureCoord.y)) * .15;
        sum += ownColor * .16;
        sum += texture2D(uTexture, vec2(vTextureCoord.x + uBlurSize, vTextureCoord.y)) * .15;
        sum += texture2D(uTexture, vec2(vTextureCoord.x + 2.*uBlurSize, vTextureCoord.y)) * .12;
        sum += texture2D(uTexture, vec2(vTextureCoord.x + 3.*uBlurSize, vTextureCoord.y)) * .09;
        sum += texture2D(uTexture, vec2(vTextureCoord.x + 4.*uBlurSize, vTextureCoord.y)) * .05;

        // Blur in y (vertical)
        // Take nine samples, with the distance blurSize between them
        sum += texture2D(uTexture, vec2(vTextureCoord.x, vTextureCoord.y - 4.*uBlurSize)) * .05;
        sum += texture2D(uTexture, vec2(vTextureCoord.x, vTextureCoord.y - 3.*uBlurSize)) * .09;
        sum += texture2D(uTexture, vec2(vTextureCoord.x, vTextureCoord.y - 2.*uBlurSize)) * .12;
        sum += texture2D(uTexture, vec2(vTextureCoord.x, vTextureCoord.y - uBlurSize)) * .15;
        sum += ownColor * .16;
        sum += texture2D(uTexture, vec2(vTextureCoord.x, vTextureCoord.y + uBlurSize)) * .15;
        sum += texture2D(uTexture, vec2(vTextureCoord.x, vTextureCoord.y + 2.*uBlurSize)) * .12;
        sum += texture2D(uTexture, vec2(vTextureCoord.x, vTextureCoord.y + 3.*uBlurSize)) * .09;
        sum += texture2D(uTexture, vec2(vTextureCoord.x, vTextureCoord.y + 4.*uBlurSize)) * .05;

        // Increase blur with intensity!
        gl_FragColor = sum * min(.9, abs(sin(uTime))) + ownColor;
    }

    gl_FragColor *= uAlpha;
}
