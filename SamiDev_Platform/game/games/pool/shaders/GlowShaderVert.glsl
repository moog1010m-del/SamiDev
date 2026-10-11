precision mediump float;

attribute vec2 aPosition;
attribute vec2 aTexture;
uniform mat4 uProjection;
uniform mat4 uTransform;
varying vec2 vTextureCoord;

void main(void) {
    gl_Position = uProjection * uTransform * vec4(aPosition.x, aPosition.y, .0, 1.);
    vTextureCoord = aTexture;
}
