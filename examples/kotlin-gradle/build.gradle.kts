plugins { kotlin("jvm") version "2.1.21" }
repositories { mavenCentral() }
dependencies {
    testImplementation("org.junit.jupiter:junit-jupiter:5.11.4")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher:1.11.4")
}
kotlin { jvmToolchain(21) }
tasks.test { useJUnitPlatform() }
