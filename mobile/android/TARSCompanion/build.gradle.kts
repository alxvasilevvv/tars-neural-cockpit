// Top-level Gradle build for the TARSCompanion Android project.
//
// Phase L10 L2 — pairing-first slice. The actual Android Studio project
// pulls in the AGP / Compose plugins; this top-level file just declares
// versions so `./gradlew tasks` works once SDK is installed.

plugins {
    id("com.android.application") version "8.5.0" apply false
    id("org.jetbrains.kotlin.android") version "2.0.0" apply false
}

tasks.register<Delete>("clean") {
    delete(rootProject.buildDir)
}
