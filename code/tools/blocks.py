"""List fenced code blocks of a model reply with preceding context (L22.6 extraction helper)."""
import re
def blocks(text):
    lines=text.split('\n'); out=[]; i=0
    while i<len(lines):
        m=re.match(r'^\s*(`{3,}|~{3,})\s*([^\s`]*)',lines[i])
        if m:
            fence=m.group(1); lang=m.group(2); j=i+1
            while j<len(lines) and not re.match(r'^\s*'+re.escape(fence[0])+'{%d,}\s*$'%len(fence),lines[j]): j+=1
            ctx=[l for l in lines[max(0,i-4):i] if l.strip()][-2:]
            out.append({'lang':lang,'ctx':ctx,'code':'\n'.join(lines[i+1:j])+'\n','start':i+1})
            i=j+1
        else: i+=1
    return out
