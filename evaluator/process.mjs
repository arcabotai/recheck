import { spawn } from 'node:child_process';
import { performance } from 'node:perf_hooks';

// Trusted evaluator infrastructure only. Candidate JSON never controls argv.
export function runBoundedProcess(args,input,{timeoutMs=1000,maxOutputBytes=65536}={}) {
  if (!Number.isInteger(timeoutMs) || timeoutMs<1 || timeoutMs>10000) throw new Error('Invalid timeout');
  if (!Number.isInteger(maxOutputBytes) || maxOutputBytes<1 || maxOutputBytes>65536) throw new Error('Invalid output limit');
  return new Promise(resolve=> {
    const start=performance.now();
    const stdoutChunks=[],stderrChunks=[];
    let bytes=0,errorCode=null,timer;
    const child=spawn(process.execPath,['--max-old-space-size=32','--disable-proto=throw',...args],{env:{},stdio:['pipe','pipe','pipe'],cwd:new URL('.',import.meta.url)});
    let settled=false;
    function finish(exitCode,signal) {
      if (settled) return;
      settled=true; clearTimeout(timer);
      resolve({stdout:Buffer.concat(stdoutChunks).toString('utf8'),stderr:Buffer.concat(stderrChunks).toString('utf8'),exitCode,signal,errorCode,pid:child.pid??null,durationMs:Math.round(performance.now()-start)});
    }
    function stop(code) { if (!errorCode) errorCode=code; child.kill('SIGKILL'); }
    timer=setTimeout(()=>stop('timeout'),timeoutMs);
    for (const [stream,key] of [[child.stdout,'stdout'],[child.stderr,'stderr']]) {
      stream.on('data',chunk=> {
        bytes+=chunk.length;
        if (bytes>maxOutputBytes) { stop('output_limit'); return; }
        (key==='stdout'?stdoutChunks:stderrChunks).push(chunk);
      });
    }
    child.on('error',()=> {errorCode='executor_unavailable'; finish(null,null);});
    // Resolve only after close: timed-out processes must actually be reaped.
    child.on('close',finish);
    child.stdin.on('error',()=>{});
    child.stdin.end(input);
  });
}
