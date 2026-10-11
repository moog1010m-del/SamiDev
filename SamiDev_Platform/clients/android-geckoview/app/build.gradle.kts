plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.samidev.platform"
    compileSdk = 36
    defaultConfig {
        applicationId = "com.samidev.platform"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"
        buildConfigField("String", "PLATFORM_URL", "\"https://game.example.com/platform/\"")
    }
    buildFeatures { buildConfig = true }
}

dependencies {
    implementation("androidx.appcompat:appcompat:1.7.1")
    implementation("org.mozilla.geckoview:geckoview:${property("geckoviewVersion")}")
}
