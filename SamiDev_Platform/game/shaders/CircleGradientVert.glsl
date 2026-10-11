attribute vec4 aPosition;
uniform mat4 uProjection;
uniform mat4 uTransform;

void main() {
    gl_Position = uProjection * uTransform * vec4(aPosition.x, aPosition.y, 0.0, 1.0);
}
