#!/bin/bash

echo "🔧 Fixing macOS Python SSL Certificates"
echo "========================================"
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
echo "✓ Found Python $PYTHON_VERSION"
echo ""

# Method 1: Upgrade certifi
echo "📦 Method 1: Upgrading certifi package..."
pip3 install --upgrade certifi
echo ""

# Method 2: Run macOS Python certificate installer
echo "🍎 Method 2: Running macOS certificate installer..."
CERT_SCRIPT="/Applications/Python $PYTHON_VERSION/Install Certificates.command"

if [ -f "$CERT_SCRIPT" ]; then
    echo "Found certificate installer at: $CERT_SCRIPT"
    "$CERT_SCRIPT"
    echo "✓ Certificates installed"
else
    echo "⚠️  Certificate installer not found at expected location"
    echo "   Looking for alternative paths..."
    
    # Try to find it
    find /Applications -name "Install Certificates.command" 2>/dev/null | while read path; do
        echo "   Found: $path"
        "$path"
    done
fi
echo ""

# Method 3: Set environment variable
echo "🔐 Method 3: Setting certifi path..."
CERT_PATH=$(python3 -c "import certifi; print(certifi.where())")
echo "export SSL_CERT_FILE=$CERT_PATH" >> ~/.zshrc
echo "export SSL_CERT_FILE=$CERT_PATH" >> ~/.bash_profile
echo "✓ Added SSL_CERT_FILE to shell configs"
echo ""

# Test
echo "🧪 Testing SSL connection..."
python3 << 'EOF'
import ssl
import urllib.request

try:
    context = ssl.create_default_context()
    with urllib.request.urlopen('https://api.jup.ag', context=context, timeout=5) as response:
        print("✅ SSL verification working!")
except Exception as e:
    print(f"❌ Still having issues: {e}")
    print("\nTry running this manually:")
    print("  sudo /Applications/Python*/Install\\ Certificates.command")
EOF

echo ""
echo "========================================"
echo "Done! Restart your terminal and try again."
echo "If issues persist, run: sudo /Applications/Python*/Install\ Certificates.command"
