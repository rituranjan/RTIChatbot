#!/usr/bin/env bash
exec bash "$(cd "$(dirname "$0")/../deployment" && pwd)/configure_ssl.sh" "$@"
