"""Read-only decoder of this repository's packed MQL4 POD journal.

The trusted local Types.mqh describes layout; uploaded files provide bytes only.
Every header, record size, FNV checksum and filename/sequence must agree before
any event is used. This is not cryptographic proof of broker provenance.
"""
import ctypes
from functools import lru_cache
import re
import struct
from pathlib import Path

LOGIC_VERSION=2026101707
SCHEMA=2

TYPES=Path(__file__).resolve().parents[1]/"mt4/Include/EURUSD_M5_V223/Types.mqh"
HEADER=struct.Struct("<5i")
MAGIC=1112494385


def checksum(content):
    value=2166136261
    for byte in content:
        value=((value^byte)*16777619)&0xffffffff
    return value


@lru_cache(maxsize=1)
def layouts():
    source=TYPES.read_text()
    constants={k:int(v) for k,v in re.findall(r"#define\s+(\w+)\s+(\d+)\b",source)}
    types={"int":ctypes.c_int32,"uint":ctypes.c_uint32,"long":ctypes.c_int64,
           "datetime":ctypes.c_int64,"double":ctypes.c_double,"bool":ctypes.c_bool}
    for name,body in re.findall(r"struct\s+(\w+)\s*\{([^{}]*)\};",source,re.S):
        fields=[]
        for declaration in body.split(';'):
            declaration=declaration.strip()
            if not declaration:continue
            match=re.fullmatch(r"(\w+)\s+(\w+)(?:\[(\w+)\])?",declaration)
            if not match or match[1] not in types:
                raise ValueError(f"Unsupported trusted POD declaration: {declaration}")
            kind=types[match[1]]
            if match[3]:
                count=constants.get(match[3],int(match[3]) if match[3].isdigit() else 0)
                if not 1<=count<=10000:raise ValueError("Unsupported array length")
                kind=kind*count
            fields.append((match[2],kind))
        types[name]=type(name,(ctypes.LittleEndianStructure,),{"_pack_":1,"_fields_":fields})
    return types


def plain(value):
    if isinstance(value,ctypes.Structure):
        return {name:plain(getattr(value,name)) for name,_ in value._fields_}
    if isinstance(value,ctypes.Array):return [plain(item) for item in value]
    return value


def decode_bytes(content,expected_sequence=None,logic_version=LOGIC_VERSION,compact=False):
    if logic_version!=LOGIC_VERSION:
        raise ValueError("Unsupported native logic version")
    types=layouts();state_type=types["BORuntimeState"];event_type=types["BOEvent"]
    state_size,event_size=ctypes.sizeof(state_type),ctypes.sizeof(event_type)
    if len(content)!=HEADER.size+state_size+event_size+4:
        raise ValueError("Native journal length differs from trusted POD layout")
    if HEADER.unpack_from(content)!=(MAGIC,SCHEMA,logic_version,state_size,event_size):
        raise ValueError("Native journal magic/version/layout mismatch")
    if checksum(content[:-4])!=struct.unpack_from('<I',content,len(content)-4)[0]:
        raise ValueError("Native journal FNV checksum mismatch")
    native_state=state_type.from_buffer_copy(content,HEADER.size)
    event=plain(event_type.from_buffer_copy(content,HEADER.size+state_size))
    if compact:
        # All bytes still pass FNV. Only avoid constructing unused pending-slot
        # dictionaries; START/LOCK retain the original closed anchor fields.
        state=dict(sequence=native_state.sequence,configHash=native_state.configHash,
            feedHash=native_state.feedHash,paused=native_state.paused,
            current=plain(native_state.current) if event['kind'] in (1,3) else dict(
                canceled=native_state.current.canceled,analysisStart=native_state.current.analysisStart,
                targetTime=native_state.current.targetTime,lastQuoteMs=native_state.current.lastQuoteMs,
                exists=native_state.current.exists,entered=native_state.current.entered,
                locked=native_state.current.locked,lockedAtMs=native_state.current.lockedAtMs))
    else:state=plain(native_state)
    if expected_sequence is not None and state["sequence"]!=expected_sequence:
        raise ValueError("Native journal filename/sequence mismatch")
    if event["kind"] not in range(1,9) or event["reason"] not in range(32):
        raise ValueError("Native event contains unsupported kind/reason")
    return {"state":state,"event":event}


def event_paths(directory):
    return sorted(Path(directory).glob('event_*.bin'))


def iter_directory(directory,logic_version=LOGIC_VERSION,*,paths=None,on_record=None,compact=False):
    previous=None
    for path in event_paths(directory) if paths is None else paths:
        match=re.fullmatch(r"event_(\d{12})\.bin",path.name)
        if not match:raise ValueError("Unexpected native journal filename")
        sequence=int(match[1])
        if previous is not None and sequence!=previous+1:
            raise ValueError("Native journal sequence gap")
        content=path.read_bytes()
        record=decode_bytes(content,sequence,logic_version,compact=compact)
        if on_record is not None:on_record(path,content)
        yield record
        previous=sequence
    if previous is None:raise ValueError("No native records")


def read_directory(directory,logic_version=LOGIC_VERSION):
    return list(iter_directory(directory,logic_version))
