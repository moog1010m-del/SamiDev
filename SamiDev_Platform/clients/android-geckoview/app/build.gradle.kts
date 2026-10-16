plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

val configuredPlatformUrl = providers.gradleProperty("samidevPlatformUrl").orNull
require(!configuredPlatformUrl.isNullOrBlank()) {
    "Set -PsamidevPlatformUrl=https://YOUR_REAL_HOST/platform/ before building"
}
val platformUri = java.net.URI(configuredPlatformUrl)
require(platformUri.scheme == "https" && !platformUri.host.isNullOrBlank() &&
    platformUri.host !in setOf("game.example.com", "example.com") &&
    platformUri.userInfo == null && platformUri.rawQuery == null && platformUri.rawFragment == null &&
    platformUri.path in setOf("", "/", "/platform/")) { "Invalid HTTPS platform URL" }
val platformUrl = platformUri.resolve("/platform/").toASCIIString()

android {
    namespace = "com.samidev.platform"
    compileSdk = 36
    defaultConfig {
        applicationId = "com.samidev.platform"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"
        buildConfigField("String", "PLATFORM_URL", "\"$platformUrl\"")
    }
    buildFeatures { buildConfig = true }
}

dependencies {
    implementation("androidx.appcompat:appcompat:1.7.1")
    implementation("org.mozilla.geckoview:geckoview:${property("geckoviewVersion")}")
}
