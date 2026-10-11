precision mediump float;

varying vec2 vTextureCoord;

uniform sampler2D uTexture;
uniform vec2 uTextureInvRes;
uniform float uStrength;
uniform vec4 uColor;
uniform float uDiscardAlpha;

void main(void) {
    vec4 ownColor = texture2D(uTexture, vTextureCoord);

    if (ownColor.w > uDiscardAlpha) discard;

    vec4 curColor;
    float totalAlpha = 0.;
    float maxTotalAlpha = 0.;
    float cosAngle;
    float sinAngle;
    for (float angle=0.; angle<=PI_2; angle+=QUALITY) {
       cosAngle = cos(angle);
       sinAngle = sin(angle);
       for (float curDistance = 1.; curDistance <= DISTANCE; curDistance+=DIST_STEP) {
           curColor = texture2D(uTexture, vec2(vTextureCoord.x + cosAngle * curDistance * uTextureInvRes.x, vTextureCoord.y + sinAngle * curDistance * uTextureInvRes.y));
           totalAlpha += (DISTANCE - curDistance) * curColor.a;
           maxTotalAlpha += (DISTANCE - curDistance);
       }
    }
    maxTotalAlpha = max(maxTotalAlpha, .0001);
    ownColor.a = max(ownColor.a, .0001);
    ownColor.rgb = ownColor.rgb / ownColor.a;
    float outerGlowAlpha = (totalAlpha / maxTotalAlpha) * uStrength * (1. - ownColor.a);
    float resultAlpha = (ownColor.a + outerGlowAlpha);

    gl_FragColor = vec4(mix(ownColor.rgb, uColor.rgb, outerGlowAlpha / resultAlpha) * resultAlpha, resultAlpha);
}
