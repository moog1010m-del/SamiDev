import java.util.Properties
import java.io.FileInputStream

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

val keystoreProperties = Properties()
val keystoreFile = rootProject.file("key.properties")
if (keystoreFile.exists()) keystoreProperties.load(FileInputStream(keystoreFile))
gradle.taskGraph.whenReady {
    if (allTasks.any { it.name.contains("Release") } && !keystoreFile.exists()) {
        throw GradleException("Release signing requires android/key.properties")
    }
}
android {
    namespace = "com.samidev.platform"
    compileSdk = maxOf(36, flutter.compileSdkVersion)
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        // Preserve the registered package: changing it also requires OAuth and Play configuration.
        applicationId = "com.samidev.platform"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = maxOf(36, flutter.targetSdkVersion)
        // Public Firebase application configuration, never service-account keys.
        // Native resources let FCM receive notifications after process death.
        // Registration remains opt-in via firebase_messaging_auto_init_enabled=false.
        val pushApp = System.getenv("SAMIDEV_FIREBASE_ANDROID_APP_ID")?.trim().orEmpty()
        val pushProject = System.getenv("SAMIDEV_FIREBASE_PROJECT_ID")?.trim().orEmpty()
        val pushKey = System.getenv("SAMIDEV_FIREBASE_API_KEY")?.trim().orEmpty()
        val pushSender = System.getenv("SAMIDEV_FIREBASE_MESSAGING_SENDER_ID")?.trim().orEmpty()
        if (listOf(pushApp, pushProject, pushKey, pushSender).all { it.isNotEmpty() }) {
            resValue("string", "google_app_id", pushApp)
            resValue("string", "google_api_key", pushKey)
            resValue("string", "gcm_defaultSenderId", pushSender)
            resValue("string", "project_id", pushProject)
        }
        // Uses the version code from pubspec.yaml. When using split APKs, 1000 * ABI_VERSION
        // is added automatically by Flutter. (https://developer.android.com/studio/build/configure-apk-splits#configure-APK-versions)
        // You can force using the value of versionCode by specifying the `-P force-version-code-ignoring-abi=true`
        // flag during build.
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        create("release") {
            if (keystoreFile.exists()) {
                keyAlias = keystoreProperties["keyAlias"] as String
                keyPassword = keystoreProperties["keyPassword"] as String
                storeFile = file(keystoreProperties["storeFile"] as String)
                storePassword = keystoreProperties["storePassword"] as String
            }
        }
    }
    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("release")
            isDebuggable = false
            isMinifyEnabled = true
            isShrinkResources = true
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}

val verifyRuntimeAssets by tasks.registering {
    doLast {
        val appRoot = rootProject.projectDir.parentFile
        val required = listOf("runtime-manifest.json", "runtime/platform/index.html",
            "runtime/platform/platform.js", "runtime/browser-runtime.js", "runtime/main.js",
            "runtime/games/crazy8/main.js", "runtime/games/pool/main.js", "runtime/games/tablesoccer/main.js")
        val missing = required.filter { val file = appRoot.resolve("assets/$it"); !file.isFile || file.length() == 0L }
        if (missing.isNotEmpty()) throw GradleException(
            "Runtime assets are missing. From SamiDev_Flutter run: python tool/sync_assets.py, then rebuild. Missing: ${missing.joinToString()}")
    }
}
tasks.matching { it.name == "preBuild" || it.name.startsWith("compileFlutterBuild") }.configureEach {
    dependsOn(verifyRuntimeAssets)
}
