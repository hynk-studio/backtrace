"""Authored process fixture shipped only by the free CPU bundle, never production."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import sys

MARKER='backtrace-authored-cpu-fixture.txt'


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def reply(self,code,value):
        data=json.dumps(value).encode()
        self.send_response(code);self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    def do_GET(self):
        if self.path=='/health':return self.reply(200,{})
        if self.path=='/v1/models':return self.reply(200,{'data':[{'id':'/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2'}]})
        if self.path!='/backtrace/split-runtime-config':return self.reply(404,{})
        self.reply(503 if '--failed-readiness' in sys.argv else 200,
                   {'status':'AUTHORED_CPU','model_execution':False})
    def do_POST(self):
        try:
            if self.path!='/v1/chat/completions':raise ValueError('chat only')
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            names={t['function']['name'] for t in body.get('tools',[])}
            acknowledgements=[m for m in body['messages'] if m['role']=='tool']
            step=len(acknowledgements);name=None;arguments={}
            if 'submit_patch' in names:
                if step==0:
                    name='run_command';arguments={'command':"python3 -c \"from pathlib import Path; p=Path('"+MARKER+"'); assert not p.exists(); p.write_text('authored CPU fixture\\n')\""}
                elif step==1:name='code_analyzer_agent';arguments={'request':'Read '+MARKER+' and report its contents.'}
                elif step==2:name='submit_patch'
                elif step!=3:raise ValueError('unexpected root fixture step')
            elif 'read_file' in names:
                if step==0:name='read_file';arguments={'filepath':MARKER}
                elif step!=1:raise ValueError('unexpected delegate fixture step')
            else:raise ValueError('unexpected fixture role')
            if name and name not in names:raise ValueError('original tool missing')
            message={'role':'assistant','content':None if name else 'Authored CPU fixture complete.'}
            if name:message['tool_calls']=[{'id':'call_'+str(step),'type':'function',
                'function':{'name':name,'arguments':json.dumps(arguments)}}]
            envelope={'id':'authored-cpu','object':'chat.completion','created':0,'model':body['model'],
                'choices':[{'index':0,'message':message,'finish_reason':'tool_calls' if name else 'stop'}],
                'usage':{'prompt_tokens':11,'completion_tokens':7,'total_tokens':18,
                         'completion_tokens_details':{'reasoning_tokens':3},
                         'prompt_tokens_details':{'cached_tokens':0}}}
            if not body.get('stream'):return self.reply(200,envelope)
            if body.get('stream_options')!={'include_usage':True}:raise ValueError('stream usage required')
            delta=dict(message)
            if name:delta['tool_calls'][0]['index']=0
            chunk={k:v for k,v in envelope.items() if k not in ('choices','usage')}
            chunk['object']='chat.completion.chunk'
            chunk['choices']=[{'index':0,'delta':delta,'finish_reason':None}]
            terminal={**chunk,'choices':[{'index':0,'delta':{},'finish_reason':envelope['choices'][0]['finish_reason']}],
                      'usage':envelope['usage']}
            data=('data: '+json.dumps(chunk)+'\n\ndata: '+json.dumps(terminal)+'\n\ndata: [DONE]\n\n').encode()
            self.send_response(200);self.send_header('Content-Type','text/event-stream')
            self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        except Exception as error:self.reply(400,{'error':{'message':type(error).__name__}})


if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',int(sys.argv[1])),Handler).serve_forever()
