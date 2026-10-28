#!/usr/bin/env bash
exec bash "$(cd "$(dirname "$0")/../deployment" && pwd)/install_ssl.sh" "$@"
