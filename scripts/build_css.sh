#!/usr/bin/env bash
# Build Tailwind CSS (standalone CLI — no Node.js runtime needed)
# Install: https://tailwindcss.com/docs/installation
set -euo pipefail

echo "🎨 Building Tailwind CSS..."

if command -v tailwindcss &> /dev/null; then
    tailwindcss \
        -i app/static/css/input.css \
        -o app/static/css/style.css \
        --minify
    echo "✅ CSS built: app/static/css/style.css"
else
    echo "⚠️  Tailwind CLI not found."
    echo "   Install standalone: https://tailwindcss.com/docs/installation"
    echo "   Or use CDN fallback (already in style.css)"
fi
