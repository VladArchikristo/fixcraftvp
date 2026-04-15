#!/usr/bin/env node
/**
 * Generate app icons and splash screen from SVG sources.
 * Usage: node scripts/generate-icons.js
 * Requires: npm install --save-dev sharp
 */

const fs = require('fs');
const path = require('path');

async function main() {
  let sharp;
  try {
    sharp = require('sharp');
  } catch {
    console.log('Installing sharp...');
    require('child_process').execSync('npm install --save-dev sharp', { stdio: 'inherit' });
    sharp = require('sharp');
  }

  const assetsDir = path.join(__dirname, '..', 'assets');

  // Icon: 1024x1024
  const iconSvg = fs.readFileSync(path.join(assetsDir, 'icon.svg'));
  await sharp(iconSvg)
    .resize(1024, 1024)
    .png()
    .toFile(path.join(assetsDir, 'icon.png'));
  console.log('icon.png generated (1024x1024)');

  // Adaptive icon (same as icon for foreground)
  await sharp(iconSvg)
    .resize(1024, 1024)
    .png()
    .toFile(path.join(assetsDir, 'adaptive-icon.png'));
  console.log('adaptive-icon.png generated (1024x1024)');

  // Favicon: 48x48
  await sharp(iconSvg)
    .resize(48, 48)
    .png()
    .toFile(path.join(assetsDir, 'favicon.png'));
  console.log('favicon.png generated (48x48)');

  // Splash: 1284x2778 (iPhone 14 Pro Max)
  const splashSvg = fs.readFileSync(path.join(assetsDir, 'splash.svg'));
  await sharp(splashSvg)
    .resize(1284, 2778)
    .png()
    .toFile(path.join(assetsDir, 'splash.png'));
  console.log('splash.png generated (1284x2778)');

  console.log('\nAll assets generated successfully!');
}

main().catch(console.error);
