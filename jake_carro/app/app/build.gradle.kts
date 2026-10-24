import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

// Senha da chave fica fora do git (keystore/chave.properties).
val chave = Properties().apply {
    val f = rootProject.file("keystore/chave.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}

android {
    namespace = "br.zati.jakecarro"
    compileSdk = 34

    defaultConfig {
        applicationId = "br.zati.jakecarro"
        minSdk = 26
        targetSdk = 34
        versionCode = (project.findProperty("versao") as String?)?.toInt() ?: 1
        versionName = "0.1.$versionCode"
        buildConfigField("String", "SERVIDOR", "\"https://carro.amiartejoias.com.br\"")
        buildConfigField("String", "TOKEN", "\"${chave.getProperty("token", "")}\"")
    }

    signingConfigs {
        create("jake") {
            storeFile = rootProject.file("keystore/jake-carro.jks")
            storePassword = chave.getProperty("senha", "")
            keyAlias = "jakecarro"
            keyPassword = chave.getProperty("senha", "")
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("jake")
        }
    }

    buildFeatures { buildConfig = true }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    implementation(files("libs/spotify-app-remote-release-0.8.0.aar"))
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("com.google.code.gson:gson:2.10.1")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("ai.picovoice:porcupine-android:4.0.2")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
}
