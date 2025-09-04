#!/bin/bash

echo "🚀 Building GoalServe Sports Betting Platform Frontend..."

# Copy static files to build directory
echo "📁 Copying static files..."
mkdir -p build
cp -r ../src/static/* build/

# Create a simple index redirect if needed
echo "📝 Creating build manifest..."
echo "Frontend build completed at $(date)" > build/build-info.txt

echo "✅ Frontend build completed successfully!"
echo "📁 Build directory: ./build"
echo "🌐 Ready for Cloudflare Pages deployment!"
