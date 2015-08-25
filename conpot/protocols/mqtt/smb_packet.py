#********************************************************************************
#*                               Dionaea
#*                           - catches bugs -
#*
#*
#*
#* Copyright (C) 2010  Markus Koetter
#* Copyright (C) 2009  Paul Baecher & Markus Koetter & Mark Schloesser
#*
#* This program is free software; you can redistribute it and/or
#* modify it under the terms of the GNU General Public License
#* as published by the Free Software Foundation; either version 2
#* of the License, or (at your option) any later version.
#*
#* This program is distributed in the hope that it will be useful,
#* but WITHOUT ANY WARRANTY; without even the implied warranty of
#* MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#* GNU General Public License for more details.
#*
#* You should have received a copy of the GNU General Public License
#* along with this program; if not, write to the Free Software
#* Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#*
#*
#*             contact nepenthesdev@gmail.com
#*
#*******************************************************************************/
#*  This file was part of Scapy
#*  See http://www.secdev.org/projects/scapy for more informations
#*  Copyright (C) Philippe Biondi <phil@secdev.org>
#*  This program is published under a GPLv2 license
#*******************************************************************************

import time
import itertools
import logging

logger = logging.getLogger('scapy')
logger.setLevel(logging.DEBUG)


from fieldtypes import StrField, ConditionalField
from helpers import VolatileValue, Gen, SetGen, BasePacket


######################################
## Packet abstract and base classes ##
######################################

class Packet_metaclass(type):
    def __new__(cls, name, bases, dct):
        if "fields_desc" in dct: # perform resolution of references to other packets
            current_fld = dct["fields_desc"]
            resolved_fld = []
            for f in current_fld:
                if isinstance(f, Packet_metaclass): # reference to another fields_desc
                    for f2 in f.fields_desc:
                        resolved_fld.append(f2)
                else:
                    resolved_fld.append(f)
        else: # look for a field_desc in parent classes
            resolved_fld = None
            for b in bases:
                if hasattr(b,"fields_desc"):
                    resolved_fld = b.fields_desc
                    break

        if resolved_fld: # perform default value replacements
            final_fld = []
            for f in resolved_fld:
                if f.name in dct:
                    f = f.copy()
                    f.default = dct[f.name]
                    del(dct[f.name])
                final_fld.append(f)

            dct["fields_desc"] = final_fld

        newcls = super(Packet_metaclass, cls).__new__(cls, name, bases, dct)
        if hasattr(newcls,"register_variant"):
            newcls.register_variant()
        for f in newcls.fields_desc:
            f.register_owner(newcls)
        return newcls

    def __getattr__(self, attr):
        for k in self.fields_desc:
            if k.name == attr:
                return k
        raise AttributeError(attr)

    def __call__(cls, *args, **kargs):
        if "dispatch_hook" in cls.__dict__:
            cls =  cls.dispatch_hook(*args, **kargs)
        i = cls.__new__(cls, cls.__name__, cls.__bases__, cls.__dict__)
        i.__init__(*args, **kargs)
        return i


class NewDefaultValues(Packet_metaclass):
    """NewDefaultValues is deprecated (not needed anymore)

    remove this:
        __metaclass__ = NewDefaultValues
    and it should still work.
    """
    def __new__(cls, name, bases, dct):
        from .error import log_loading
        import traceback
        try:
            for tb in traceback.extract_stack()+[("??",-1,None,"")]:
                f,l,_,line = tb
                if line.startswith("class"):
                    break
        except:
            f,l="??",-1
            raise
        log_loading.warning("Deprecated (no more needed) use of NewDefaultValues  (%s l. %i)." % (f,l))

        return super(NewDefaultValues, cls).__new__(cls, name, bases, dct)


class Packet(BasePacket):
    __metaclass__ = Packet_metaclass
    name = None

    fields_desc = []

    aliastypes = []
    overload_fields = {}

    underlayer = None

    payload_guess = []
    initialized = 0
    show_indent=1
    explicit = 0

    @classmethod
    def upper_bonds(cls):
        for fval,upper in cls.payload_guess:
            print("%-20s  %s" % (upper.__name__, ", ".join("%-12s" % ("%s=%r"%i) for i in fval.items())))

    @classmethod
    def lower_bonds(cls):
        for lower,fval in cls.overload_fields.items():
            print("%-20s  %s" % (lower.__name__, ", ".join("%-12s" % ("%s=%r"%i) for i in fval.items())))

    def __init__(self, _pkt="", _ctx=None, post_transform=None, _internal=0, _underlayer=None, **fields):
        if _ctx:
            self.ctx = _ctx
        self.time = time.time()
        self.sent_time = 0
        if self.name is None:
            self.name = self.__class__.__name__
        self.aliastypes = [self.__class__] + self.aliastypes
        self.default_fields = {}
        self.overloaded_fields = {}
        self.fields = {}
        self.fieldtype = {}
        self.packetfields = []
        self.__dict__["payload"] = NoPayload()
        self.init_fields()
        self.underlayer = _underlayer
        self.initialized = 1
        if _pkt:
            self.dissect(_pkt)
            if not _internal:
                self.dissection_done(self)
        for f in list(fields.keys()):
            self.fields[f] = self.get_field(f).any2i(self,fields[f])
        if type(post_transform) is list:
            self.post_transforms = post_transform
        elif post_transform is None:
            self.post_transforms = []
        else:
            self.post_transforms = [post_transform]

    def init_fields(self):
        self.do_init_fields(self.fields_desc)

    def do_init_fields(self, flist):
        for f in flist:
            self.default_fields[f.name] = f.default
            self.fieldtype[f.name] = f
            if f.holds_packets:
                self.packetfields.append(f)

    def dissection_done(self,pkt):
        """DEV: will be called after a dissection is completed"""
        self.post_dissection(pkt)
        self.payload.dissection_done(pkt)

    def post_dissection(self, pkt):
        """DEV: is called after the dissection of the whole packet"""
        pass

    def get_field(self, fld):
        """DEV: returns the field instance from the name of the field"""
        return self.fieldtype[fld]

    def add_payload(self, payload):
        if payload is None:
            return
        elif not isinstance(self.payload, NoPayload):
            self.payload.add_payload(payload)
        else:
            if isinstance(payload, Packet):
                self.__dict__["payload"] = payload
                payload.add_underlayer(self)
                for t in self.aliastypes:
                    if t in payload.overload_fields:
                        self.overloaded_fields = payload.overload_fields[t]
                        break
            elif type(payload) is str:
                self.__dict__["payload"] = Raw(load=payload)
            else:
                raise TypeError("payload must be either 'Packet' or 'str', not [%s]" % repr(payload))

    def remove_payload(self):
        self.payload.remove_underlayer(self)
        self.__dict__["payload"] = NoPayload()
        self.overloaded_fields = {}

    def add_underlayer(self, underlayer):
        self.underlayer = underlayer

    def remove_underlayer(self, other):
        self.underlayer = None

    def copy(self):
        """Returns a deep copy of the instance."""
        clone = self.__class__()
        clone.fields = self.fields.copy()
        for k in clone.fields:
            clone.fields[k]=self.get_field(k).do_copy(clone.fields[k])
        clone.default_fields = self.default_fields.copy()
        clone.overloaded_fields = self.overloaded_fields.copy()
        clone.overload_fields = self.overload_fields.copy()
        clone.underlayer=self.underlayer
        clone.explicit=self.explicit
        clone.post_transforms=self.post_transforms[:]
        clone.__dict__["payload"] = self.payload.copy()
        clone.payload.add_underlayer(clone)
        return clone

    def getfieldval(self, attr):
        if attr in self.fields:
            return self.fields[attr]
        if attr in self.overloaded_fields:
            return self.overloaded_fields[attr]
        if attr in self.default_fields:
            return self.default_fields[attr]
        return self.payload.getfieldval(attr)

    def getfield_and_val(self, attr):
        if attr in self.fields:
            return self.get_field(attr),self.fields[attr]
        if attr in self.overloaded_fields:
            return self.get_field(attr),self.overloaded_fields[attr]
        if attr in self.default_fields:
            return self.get_field(attr),self.default_fields[attr]
        return self.payload.getfield_and_val(attr)

    def __getattr__(self, attr):
        if self.initialized:
            fld,v = self.getfield_and_val(attr)
            if fld is not None:
                return fld.i2h(self, v)
            return v
        raise AttributeError(attr)

    def setfieldval(self, attr, val):
        if attr in self.default_fields:
            fld = self.get_field(attr)
            if fld is None:
                any2i = lambda x,y: y
            else:
                any2i = fld.any2i
            self.fields[attr] = any2i(self, val)
            self.explicit=0
        elif attr == "payload":
            self.remove_payload()
            self.add_payload(val)
        else:
            self.payload.setfieldval(attr,val)

    def __setattr__(self, attr, val):
        if self.initialized:
            try:
                self.setfieldval(attr,val)
            except AttributeError:
                pass
            else:
                return
        self.__dict__[attr] = val

    def delfieldval(self, attr):
        if attr in self.fields:
            del(self.fields[attr])
            self.explicit=0 # in case a default value must be explicited
        elif attr in self.default_fields:
            pass
        elif attr == "payload":
            self.remove_payload()
        else:
            self.payload.delfieldval(attr)

    def __delattr__(self, attr):
        if self.initialized:
            try:
                self.delfieldval(attr)
            except AttributeError:
                pass
            else:
                return
        if attr in self.__dict__:
            del(self.__dict__[attr])
        else:
            raise AttributeError(attr)

    def __repr__(self):
        s = ""
        for f in self.fields_desc:
            if isinstance(f, ConditionalField) and not f._evalcond(self):
                continue
            if f.name in self.fields:
                val = f.i2repr(self, self.fields[f.name])
            elif f.name in self.overloaded_fields:
                val =  f.i2repr(self, self.overloaded_fields[f.name])
            else:
                continue

            s += " %s%s%s" % (f.name,
                              "=",
                              val)
        return "%s%s %s %s%s%s"% ("<",
                                  self.__class__.__name__,
                                  s,
                                  "|",
                                  repr(self.payload),
                                  ">")
    def __truediv__(self, other):
        if isinstance(other, Packet):
            cloneA = self.copy()
            cloneB = other.copy()
            cloneA.add_payload(cloneB)
            return cloneA
        elif type(other) is str:
            return self/Raw(load=other)
        else:
            return other.__rdiv__(self)
    def __rdiv__(self, other):
        if type(other) is str:
            return Raw(load=other)/self
        else:
            raise TypeError
    def __mul__(self, other):
        if type(other) is int:
            return  [self]*other
        else:
            raise TypeError
    def __rmul__(self,other):
        return self.__mul__(other)

    def __bool__(self):
        return True
    def __len__(self):
        return len(self.build())
    def do_build(self):
        p=b''
        for f in self.fields_desc:
            p = f.addfield(self, p, self.getfieldval(f.name))
        return p

    def post_build(self, pkt, pay):
        """DEV: called right after the current layer is build."""
        return pkt+pay

    def build_payload(self):
        return self.payload.build(internal=1)

    def build(self,internal=0):
        if not self.explicit:
            self = next(self.__iter__())
        pkt = self.do_build()
        for t in self.post_transforms:
            pkt = t(pkt)
        pay = self.build_payload()
        p = self.post_build(pkt,pay)
        if not internal:
            pad = self.payload.getlayer(Padding)
            if pad:
                p += pad.build()
            p = self.build_done(p)
        return p

    def build_done(self, p):
        return self.payload.build_done(p)

    def extract_padding(self, s):
        """DEV: to be overloaded to extract current layer's padding. Return a couple of strings (actual layer, padding)"""
        return s,None

    def post_dissect(self, s):
        """DEV: is called right after the current layer has been dissected"""
        return s

    def pre_dissect(self, s):
        """DEV: is called right before the current layer is dissected"""
        return s

    def do_dissect(self, s):
        flist = self.fields_desc[:]
        flist.reverse()
        while s and flist:
            #print('DEBUG:', repr(self), s)
            f = flist.pop()
            s,fval = f.getfield(self, s)
            self.fields[f.name] = fval
        return s

    def do_dissect_payload(self, s):
        if s:
            cls = self.guess_payload_class(s)
            try:
                p = cls(s, _internal=1, _underlayer=self)
            except KeyboardInterrupt:
                raise
            except:
                if isinstance(cls,type) and issubclass(cls,Packet):
                    print("%s dissector failed" % cls.name)
                else:
                    print("%s.guess_payload_class() returned [%s]" % (self.__class__.__name__,repr(cls)))
                if cls is not None:
                    raise
                p = Raw(s, _internal=1, _underlayer=self)
            self.add_payload(p)

    def dissect(self, s):
        s = self.pre_dissect(s)
        s = self.do_dissect(s)
        s = self.post_dissect(s)
        payl,pad = self.extract_padding(s)
        self.do_dissect_payload(payl)
        if pad:
            self.add_payload(Padding(pad))

    def guess_payload_class(self, payload):
        """DEV: Guesses the next payload class from layer bonds. Can be overloaded to use a different mechanism."""
        for t in self.aliastypes:
            for fval, cls in t.payload_guess:
                ok = 1
                for k in list(fval.keys()):
                    if not hasattr(self, k) or not fval[k](self.getfieldval(k)):
                        ok = 0
                        break
                if ok:
                    return cls
        return self.default_payload_class(payload)

    def default_payload_class(self, payload):
        """DEV: Returns the default payload class if nothing has been found by the guess_payload_class() method."""
        return Raw

    def hide_defaults(self):
        """Removes fields' values that are the same as default values."""
        for k in list(self.fields.keys()):
            if k in self.default_fields:
                if self.default_fields[k] == self.fields[k]:
                    del(self.fields[k])
        self.payload.hide_defaults()

    def clone_with(self, payload=None, **kargs):
        pkt = self.__class__()
        pkt.explicit = 1
        pkt.fields = kargs
        pkt.time = self.time
        pkt.underlayer = self.underlayer
        pkt.overload_fields = self.overload_fields.copy()
        pkt.post_transforms = self.post_transforms
        if payload is not None:
            pkt.add_payload(payload)
        return pkt


    def __iter__(self):
        def loop(todo, done, self=self):
            if todo:
                eltname = todo.pop()
                elt = self.getfieldval(eltname)
                if not isinstance(elt, Gen):
                    if self.get_field(eltname).islist:
                        elt = SetGen([elt])
                    else:
                        elt = SetGen(elt)
                for e in elt:
                    done[eltname]=e
                    for x in loop(todo[:], done):
                        yield x
            else:
                if isinstance(self.payload,NoPayload):
                    payloads = [None]
                else:
                    payloads = self.payload
                for payl in payloads:
                    done2=done.copy()
                    for k in done2:
                        if isinstance(done2[k], VolatileValue):
                            done2[k] = done2[k]._fix()
                    pkt = self.clone_with(payload=payl, **done2)
                    yield pkt

        if self.explicit:
            todo = []
            done = self.fields
        else:
            todo = [ k for (k,v) in itertools.chain(iter(self.default_fields.items()),
                                                    iter(self.overloaded_fields.items()))
                     if isinstance(v, VolatileValue) ] + list(self.fields.keys())
            done = {}
        return loop(todo, done)

    def __gt__(self, other):
        """True if other is an answer from self (self ==> other)."""
        if isinstance(other, Packet):
            return other < self
        elif type(other) is str:
            return 1
        else:
            raise TypeError((self, other))
    def __lt__(self, other):
        """True if self is an answer from other (other ==> self)."""
        if isinstance(other, Packet):
            return self.answers(other)
        elif type(other) is str:
            return 1
        else:
            raise TypeError((self, other))

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        for f in self.fields_desc:
            if f not in other.fields_desc:
                return False
            if self.getfieldval(f.name) != other.getfieldval(f.name):
                return False
        return self.payload == other.payload

    def __ne__(self, other):
        return not self.__eq__(other)

    def hashret(self):
        """DEV: returns a string that has the same value for a request and its answer."""
        return self.payload.hashret()
    def answers(self, other):
        """DEV: true if self is an answer from other"""
        if other.__class__ == self.__class__:
            return self.payload.answers(other.payload)
        return 0

    def haslayer(self, cls):
        """true if self has a layer that is an instance of cls. Superseded by "cls in self" syntax."""
        if self.__class__ == cls or self.__class__.__name__ == cls:
            return 1
        for f in self.packetfields:
            fvalue_gen = self.getfieldval(f.name)
            if fvalue_gen is None:
                continue
            if not f.islist:
                fvalue_gen = SetGen(fvalue_gen,_iterpacket=0)
            for fvalue in fvalue_gen:
                if isinstance(fvalue, Packet):
                    ret = fvalue.haslayer(cls)
                    if ret:
                        return ret
        return self.payload.haslayer(cls)
    def getlayer(self, cls, nb=1, _track=None):
        """Return the nb^th layer that is an instance of cls."""
        if type(cls) is int:
            nb = cls+1
            cls = None
        if type(cls) is str and "." in cls:
            ccls,fld = cls.split(".",1)
        else:
            ccls,fld = cls,None
        if cls is None or self.__class__ == cls or self.__class__.name == ccls:
            if nb == 1:
                if fld is None:
                    return self
                else:
                    return self.getfieldval(fld)
            else:
                nb -=1
        for f in self.packetfields:
            fvalue_gen = self.getfieldval(f.name)
            if fvalue_gen is None:
                continue
            if not f.islist:
                fvalue_gen = SetGen(fvalue_gen,_iterpacket=0)
            for fvalue in fvalue_gen:
                if isinstance(fvalue, Packet):
                    track=[]
                    ret = fvalue.getlayer(cls, nb, _track=track)
                    if ret is not None:
                        return ret
                    nb = track[0]
        return self.payload.getlayer(cls,nb,_track=_track)

    def firstlayer(self):
        q = self
        while q.underlayer is not None:
            q = q.underlayer
        return q

    def __getitem__(self, cls):
        if type(cls) is slice:
            lname = cls.start
            if cls.stop:
                ret = self.getlayer(cls.start, cls.stop)
            else:
                ret = self.getlayer(cls.start)
            if ret is None and cls.step is not None:
                ret = cls.step
        else:
            lname=cls
            ret = self.getlayer(cls)
        if ret is None:
            if type(lname) is Packet_metaclass:
                lname = lname.__name__
            elif type(lname) is not str:
                lname = repr(lname)
            raise IndexError("Layer [%s] not found" % lname)
        return ret

    def __delitem__(self, cls):
        del(self[cls].underlayer.payload)

    def __setitem__(self, cls, val):
        self[cls].underlayer.payload = val

    def __contains__(self, cls):
        """"cls in self" returns true if self has a layer which is an instance of cls."""
        return self.haslayer(cls)

    def route(self):
        return (None,None,None)

    def fragment(self, *args, **kargs):
        return self.payload.fragment(*args, **kargs)

    def size(self):
        x = 0
        for f in self.fields_desc:
            x += f.size(self, self.getfieldval(f.name))
        return x


    def display(self,*args,**kargs):  # Deprecated. Use show()
        """Deprecated. Use show() method."""
        self.show(*args,**kargs)
    def show(self, indent=3, lvl="", label_lvl="", goff=0):
        """Prints a hierarchical view of the packet. "indent" gives the size of indentation for each layer."""
#        return
        logger.debug("%s%s %s sizeof(%i) %s " % (label_lvl,
                              "###[",
                              self.name, self.size(),
                              "]###"))
        off=0
        for f in self.fields_desc:
            size = 0
            if isinstance(f, ConditionalField) and not f._evalcond(self):
                continue
            fvalue = self.getfieldval(f.name)
            if isinstance(fvalue, Packet) or (f.islist and f.holds_packets and type(fvalue) is list):
                logger.debug("%s  \\%-10s\\" % (label_lvl+lvl, f.name))
                fvalue_gen = SetGen(fvalue,_iterpacket=0)
                for fvalue in fvalue_gen:
                    size = fvalue.size()
                    fvalue.show(indent=indent, label_lvl=label_lvl+lvl+"   |", goff=goff)
            else:
                size = f.size(self,fvalue)
                logger.debug("%s  %-20s%s %-15s sizeof(%3i) off=%3i goff=%3i" % (label_lvl+lvl,
                                          f.name,
                                          "=",
                                          f.i2repr(self,fvalue),
                                          size,
                                          off,
                                          goff))
            off += size
            goff +=size
        self.payload.show(indent=indent, lvl=lvl+(" "*indent*self.show_indent), label_lvl=label_lvl, goff=goff)
    def show2(self):
        """Prints a hierarchical view of an assembled version of the packet, so that automatic fields are calculated (checksums, etc.)"""
        self.__class__(self.build()).show()

    def sprintf(self, fmt, relax=1):
        """sprintf(format, [relax=1]) -> str
where format is a string that can include directives. A directive begins and
ends by % and has the following format %[fmt[r],][cls[:nb].]field%.
fmt is a classic printf directive, "r" can be appended for raw substitution
(ex: IP.flags=0x18 instead of SA), nb is the number of the layer we want
(ex: for IP/IP packets, IP:2.src is the src of the upper IP layer).
Special case : "%.time%" is the creation time.
Ex : p.sprintf("%.time% %-15s,IP.src% -> %-15s,IP.dst% %IP.chksum% "
               "%03xr,IP.proto% %r,TCP.flags%")
Moreover, the format string can include conditionnal statements. A conditionnal
statement looks like : {layer:string} where layer is a layer name, and string
is the string to insert in place of the condition if it is true, i.e. if layer
is present. If layer is preceded by a "!", the result si inverted. Conditions
can be imbricated. A valid statement can be :
  p.sprintf("This is a{TCP: TCP}{UDP: UDP}{ICMP:n ICMP} packet")
  p.sprintf("{IP:%IP.dst% {ICMP:%ICMP.type%}{TCP:%TCP.dport%}}")
A side effect is that, to obtain "{" and "}" characters, you must use
"%(" and "%)".
"""

        escape = { "%": "%",
                   "(": "{",
                   ")": "}" }


        # Evaluate conditions
        while "{" in fmt:
            i = fmt.rindex("{")
            j = fmt[i+1:].index("}")
            cond = fmt[i+1:i+j+1]
            k = cond.find(":")
            if k < 0:
                raise Exception("Bad condition in format string: [%s] (read sprintf doc!)"%cond)
            cond,format = cond[:k],cond[k+1:]
            res = False
            if cond[0] == "!":
                res = True
                cond = cond[1:]
            if self.haslayer(cond):
                res = not res
            if not res:
                format = ""
            fmt = fmt[:i]+format+fmt[i+j+2:]

        # Evaluate directives
        s = ""
        while "%" in fmt:
            i = fmt.index("%")
            s += fmt[:i]
            fmt = fmt[i+1:]
            if fmt and fmt[0] in escape:
                s += escape[fmt[0]]
                fmt = fmt[1:]
                continue
            try:
                i = fmt.index("%")
                sfclsfld = fmt[:i]
                fclsfld = sfclsfld.split(",")
                if len(fclsfld) == 1:
                    f = "s"
                    clsfld = fclsfld[0]
                elif len(fclsfld) == 2:
                    f,clsfld = fclsfld
                else:
                    raise Exception
                if "." in clsfld:
                    cls,fld = clsfld.split(".")
                else:
                    cls = self.__class__.__name__
                    fld = clsfld
                num = 1
                if ":" in cls:
                    cls,num = cls.split(":")
                    num = int(num)
                fmt = fmt[i+1:]
            except:
                raise Exception("Bad format string [%%%s%s]" % (fmt[:25], fmt[25:] and "..."))
            else:
                if fld == "time":
                    val = time.strftime("%H:%M:%S.%%06i", time.localtime(self.time)) % int((self.time-int(self.time))*1000000)
                elif cls == self.__class__.__name__ and hasattr(self, fld):
                    if num > 1:
                        val = self.payload.sprintf("%%%s,%s:%s.%s%%" % (f,cls,num-1,fld), relax)
                        f = "s"
                    elif f[-1] == "r":  # Raw field value
                        val = getattr(self,fld)
                        f = f[:-1]
                        if not f:
                            f = "s"
                    else:
                        val = getattr(self,fld)
                        if fld in self.fieldtype:
                            val = self.fieldtype[fld].i2repr(self,val)
                else:
                    val = self.payload.sprintf("%%%s%%" % sfclsfld, relax)
                    f = "s"
                s += ("%"+f) % val

        s += fmt
        return s

    def mysummary(self):
        """DEV: can be overloaded to return a string that summarizes the layer.
           Only one mysummary() is used in a whole packet summary: the one of the upper layer,
           except if a mysummary() also returns (as a couple) a list of layers whose
           mysummary() must be called if they are present."""
        return ""

    def summary(self, intern=0):
        """Prints a one line summary of a packet."""
        found,s,needed = self.payload.summary(intern=1)
        if s:
            s = " / "+s
        ret = ""
        if not found or self.__class__ in needed:
            ret = self.mysummary()
            if type(ret) is tuple:
                ret,n = ret
                needed += n
        if ret or needed:
            found = 1
        if not ret:
            ret = self.__class__.__name__
        ret = "%s%s" % (ret,s)
        if intern:
            return found,ret,needed
        else:
            return ret

    def lastlayer(self,layer=None):
        """Returns the uppest layer of the packet"""
        return self.payload.lastlayer(self)

    def decode_payload_as(self,cls):
        """Reassembles the payload and decode it using another packet class"""
        s = self.payload.build()
        self.payload = cls(s, _underlayer=self)

    def command(self):
        """Returns a string representing the command you have to type to obtain the same packet"""
        f = []
        for fn,fv in list(self.fields.items()):
            fld = self.get_field(fn)
            if isinstance(fv, Packet):
                fv = fv.command()
            elif fld.islist and fld.holds_packets and type(fv) is list:
                fv = "[%s]" % ",".join( map(Packet.command, fv))
            else:
                fv = repr(fv)
            f.append("%s=%s" % (fn, fv))
        c = "%s(%s)" % (self.__class__.__name__, ", ".join(f))
        pc = self.payload.command()
        if pc:
            c += "/"+pc
        return c

class NoPayload(Packet):
    def __new__(cls, *args, **kargs):
        singl = cls.__dict__.get("__singl__")
        if singl is None:
            cls.__singl__ = singl = Packet.__new__(cls)
            Packet.__init__(singl)
        return singl
    def __init__(self, *args, **kargs):
        pass
    def dissection_done(self,pkt):
        return
    def add_payload(self, payload):
        raise Exception("Can't add payload to NoPayload instance")
    def remove_payload(self):
        pass
    def add_underlayer(self,underlayer):
        pass
    def remove_underlayer(self,other):
        pass
    def copy(self):
        return self
    def __repr__(self):
        return ""
    def __str__(self):
        return ""
    def __bool__(self):
        return False
    def build(self, internal=0):
        return b''
    def build_done(self, p):
        return p
    def getfieldval(self, attr):
        raise AttributeError(attr)
    def getfield_and_val(self, attr):
        raise AttributeError(attr)
    def setfieldval(self, attr, val):
        raise AttributeError(attr)
    def delfieldval(self, attr):
        raise AttributeError(attr)
    def __getattr__(self, attr):
        if attr in self.__dict__:
            return self.__dict__[attr]
        elif attr in self.__class__.__dict__:
            return self.__class__.__dict__[attr]
        else:
            raise AttributeError(attr)
    def hide_defaults(self):
        pass
    def __iter__(self):
        return iter([])
    def __eq__(self, other):
        if isinstance(other, NoPayload):
            return True
        return False
    def hashret(self):
        return ""
    def answers(self, other):
        return isinstance(other, NoPayload) or isinstance(other, Padding)
    def haslayer(self, cls):
        return 0
    def getlayer(self, cls, nb=1, _track=None):
        if _track is not None:
            _track.append(nb)
        return None
    def fragment(self, *args, **kargs):
        raise Exception("cannot fragment this packet")
    def show(self, indent=3, lvl="", label_lvl="", goff=0):
        pass
    def sprintf(self, fmt, relax):
        if relax:
            return "??"
        else:
            raise Exception("Format not found [%s]"%fmt)
    def summary(self, intern=0):
        return 0,"",[]
    def lastlayer(self,layer):
        return layer
    def command(self):
        return ""

####################
## packet classes ##
####################


class Raw(Packet):
    name = "Raw"
    fields_desc = [ StrField("load", "") ]
    def answers(self, other):
        return 1
#        s = str(other)
#        t = self.load
#        l = min(len(s), len(t))
#        return  s[:l] == t[:l]

class Padding(Raw):
    name = "Padding"
    def build(self, internal=0):
        if internal:
            return ""
        else:
            return Raw.build(self)

#################
## Bind layers ##
#################


def bind_bottom_up(lower, upper, __fval=None, **fval):
    if __fval is not None:
        fval.update(__fval)
    lower.payload_guess = lower.payload_guess[:]
    lower.payload_guess.append((fval, upper))


def bind_top_down(lower, upper, __fval=None, **fval):
    if __fval is not None:
        fval.update(__fval)
    upper.overload_fields = upper.overload_fields.copy()
    upper.overload_fields[lower] = fval

def bind_layers(lower, upper, __fval=None, **fval):
    """Bind 2 layers on some specific fields' values"""
    if __fval is not None:
        fval.update(__fval)
    bind_top_down(lower, upper, **fval)
    bind_bottom_up(lower, upper, **fval)

def split_bottom_up(lower, upper, __fval=None, **fval):
    if __fval is not None:
        fval.update(__fval)
    def do_filter(xxx_todo_changeme,upper=upper,fval=fval):
        (f,u) = xxx_todo_changeme
        if u != upper:
            return True
        for k in fval:
            if k not in f or f[k] != fval[k]:
                return True
        return False
    lower.payload_guess = list(filter(do_filter, lower.payload_guess))

def split_top_down(lower, upper, __fval=None, **fval):
    if __fval is not None:
        fval.update(__fval)
    if lower in upper.overload_fields:
        ofval = upper.overload_fields[lower]
        for k in fval:
            if k not in ofval or ofval[k] != fval[k]:
                return
        upper.overload_fields = upper.overload_fields.copy()
        del(upper.overload_fields[lower])

def split_layers(lower, upper, __fval=None, **fval):
    """Split 2 layers previously bound"""
    if __fval is not None:
        fval.update(__fval)
    split_bottom_up(lower, upper, **fval)
    split_top_down(lower, upper, **fval)
