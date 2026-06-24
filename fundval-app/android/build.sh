#!/bin/bash
set -e

cd "$(dirname "$0")"

PROXY_HOST="127.0.0.1"
PROXY_PORT="7891"

echo "==> Fundval Android Build"
echo "    Proxy: ${PROXY_HOST}:${PROXY_PORT}"
echo ""

export JAVA_OPTS="-Dhttp.proxyHost=${PROXY_HOST} -Dhttp.proxyPort=${PROXY_PORT} -Dhttps.proxyHost=${PROXY_HOST} -Dhttps.proxyPort=${PROXY_PORT}"
export GRADLE_OPTS="-Dhttp.proxyHost=${PROXY_HOST} -Dhttp.proxyPort=${PROXY_PORT} -Dhttps.proxyHost=${PROXY_HOST} -Dhttps.proxyPort=${PROXY_PORT}"

echo "==> Step 1: Download Gradle wrapper distribution..."
./gradlew --version 2>&1 | head -3

echo ""
echo "==> Step 2: Assemble debug APK..."
./gradlew assembleDebug \
    -Dhttp.proxyHost=${PROXY_HOST} \
    -Dhttp.proxyPort=${PROXY_PORT} \
    -Dhttps.proxyHost=${PROXY_HOST} \
    -Dhttps.proxyPort=${PROXY_PORT} \
    2>&1

if [ $? -eq 0 ]; then
    APK="app/build/outputs/apk/debug/app-debug.apk"
    if [ -f "$APK" ]; then
        echo ""
        echo "==> BUILD SUCCESS"
        echo "    APK: $(realpath "$APK")"
        echo "    Size: $(du -h "$APK" | cut -f1)"

        # Optionally install to emulator
        if command -v adb &> /dev/null && adb devices | grep -q "emulator"; then
            echo ""
            echo "==> Emulator detected, installing..."
            for emu in $(adb devices | grep emulator | awk '{print $1}'); do
                echo "    Installing to $emu..."
                adb -s "$emu" install -r "$APK"
            done
        fi
    fi
else
    echo ""
    echo "==> BUILD FAILED"
    exit 1
fi
