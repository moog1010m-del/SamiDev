import {build} from 'esbuild';
import {fileURLToPath} from 'node:url';
await build({entryPoints:[fileURLToPath(new URL('./google-auth.js',import.meta.url))],bundle:true,format:'esm',minify:true,legalComments:'eof',outfile:fileURLToPath(new URL('../../game/platform/vendor/google-auth.js',import.meta.url))});
