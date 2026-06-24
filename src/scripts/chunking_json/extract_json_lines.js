const fs = require('fs');
const readline = require('readline');
const path = require('path');

/**
 * Extract first N lines from a large JSON file
 * Usage: node extract_json_lines.js <input_file> <output_file> <line_count>
 * Example: node extract_json_lines.js E:\eve.json eve_sample_1000.jsonl 1000
 */

// Configuration
const inputFile = process.argv[2] || 'D:\\eve.json';
const outputFile = process.argv[3] || 'eve_sample_10000000.jsonl';
const lineCount = parseInt(process.argv[4]) || 10000000;

console.log(`📂 Input file: ${inputFile}`);
console.log(`💾 Output file: ${outputFile}`);
console.log(`📊 Extracting: ${lineCount.toLocaleString()} lines\n`);

// Verify input file exists
if (!fs.existsSync(inputFile)) {
  console.error(`❌ Error: Input file not found: ${inputFile}`);
  process.exit(1);
}

// Get file size for info
const fileStats = fs.statSync(inputFile);
const fileSizeGB = (fileStats.size / (1024 * 1024 * 1024)).toFixed(2);
console.log(`📏 File size: ${fileSizeGB} GB\n`);

// Create read stream and line reader
const readStream = fs.createReadStream(inputFile, { encoding: 'utf8' });
const writeStream = fs.createWriteStream(outputFile, { encoding: 'utf8' });

const rl = readline.createInterface({
  input: readStream,
  crlfDelay: Infinity // Handles both \n and \r\n line endings
});

let lineCounter = 0;
let validJsonCount = 0;
let invalidJsonCount = 0;
const startTime = Date.now();

console.log('⏳ Processing...\n');

rl.on('line', (line) => {
  if (lineCounter >= lineCount) {
    rl.close();
    readStream.destroy();
    return;
  }

  lineCounter++;

  try {
    // Validate JSON
    JSON.parse(line);
    validJsonCount++;
    // Write valid JSON line
    writeStream.write(line + '\n');
  } catch (err) {
    invalidJsonCount++;
    console.warn(`⚠️  Line ${lineCounter}: Invalid JSON - ${err.message.substring(0, 50)}`);
  }

  // Progress update every 100 lines
  if (lineCounter % 100 === 0) {
    process.stdout.write(`\r✓ Processed: ${lineCounter.toLocaleString()} lines | Valid: ${validJsonCount.toLocaleString()} | Invalid: ${invalidJsonCount.toLocaleString()}`);
  }
});

rl.on('close', () => {
  writeStream.end();
});

writeStream.on('finish', () => {
  const endTime = Date.now();
  const duration = ((endTime - startTime) / 1000).toFixed(2);

  console.log(`\n\n✅ Extraction complete!\n`);
  console.log(`📋 Summary:`);
  console.log(`   Total lines read:    ${lineCounter.toLocaleString()}`);
  console.log(`   Valid JSON records:  ${validJsonCount.toLocaleString()}`);
  console.log(`   Invalid records:     ${invalidJsonCount.toLocaleString()}`);
  console.log(`   Output file:         ${outputFile}`);
  console.log(`   Time elapsed:        ${duration}s\n`);

  // Get output file size
  const outputStats = fs.statSync(outputFile);
  const outputSizeKB = (outputStats.size / 1024).toFixed(2);
  console.log(`💾 Output file size:  ${outputSizeKB} KB`);
});

readStream.on('error', (err) => {
  console.error(`❌ Read error: ${err.message}`);
  process.exit(1);
});

writeStream.on('error', (err) => {
  console.error(`❌ Write error: ${err.message}`);
  process.exit(1);
});

rl.on('error', (err) => {
  console.error(`❌ Error: ${err.message}`);
  process.exit(1);
});
