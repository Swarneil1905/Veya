import {createHash} from 'node:crypto';
import {readFileSync,writeFileSync,readdirSync,statSync,mkdirSync} from 'node:fs';
import {join} from 'node:path';
const files=[];
function walk(path){for(const entry of readdirSync(path)){const child=join(path,entry);if(statSync(child).isDirectory())walk(child);else files.push(child);}}
walk('dist');
if(process.argv.includes('--native'))walk('src-tauri/target/release/bundle');
mkdirSync('artifacts',{recursive:true});
const hashes=files.sort().map(file=>`${createHash('sha256').update(readFileSync(file)).digest('hex')}  ${file.replaceAll('\\','/')}`);
writeFileSync('artifacts/SHA256SUMS.txt',hashes.join('\n')+'\n');
writeFileSync('artifacts/build-manifest.json',JSON.stringify({project:'relay-studio',version:'0.1.0',kind:'design-prototype',commit:process.env.GITHUB_SHA||'local-uncommitted',native:process.argv.includes('--native'),signed:false,modelInference:false,createdAt:new Date().toISOString(),files:hashes.length},null,2));
console.log(`Manifest created for ${files.length} files. This is not a signing attestation.`);
