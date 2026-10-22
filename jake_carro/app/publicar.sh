#!/bin/bash
# Compila o APK com o próximo número de versão e publica em /carro/apk.
set -e
cd "$(dirname "$0")"
REL=../releases
ATUAL=$(python3 -c "import json;print(json.load(open('$REL/versao.json'))['versao'])" 2>/dev/null || echo 0)
NOVA=$((ATUAL + 1))
export ANDROID_HOME=/opt/android-sdk
nice -n 10 ./gradlew assembleRelease -Pversao=$NOVA --no-daemon -q
cp app/build/outputs/apk/release/app-release.apk "$REL/jake-carro-$NOVA.apk"
echo "{\"versao\": $NOVA, \"nome\": \"jake-carro-$NOVA.apk\"}" > "$REL/versao.json"
echo "publicado: versão $NOVA"
