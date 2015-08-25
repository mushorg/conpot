#********************************************************************************
#*                               Dionaea
#*                           - catches bugs -
#*
#*
#*
#* Copyright (C) 2015  Tan Kean Siong
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


from smb_packet import *
from fieldtypes import *


#MQTT Control Message Types
MQTT_CONTROLMESSAGE_TYPE_CONNECT     = 0x10
MQTT_CONTROLMESSAGE_TYPE_CONNECTACK  = 0x20
MQTT_CONTROLMESSAGE_TYPE_PUBLISH     = 0x30
MQTT_CONTROLMESSAGE_TYPE_PUBLISHACK  = 0x40
MQTT_CONTROLMESSAGE_TYPE_PUBLISHRCV  = 0x50
MQTT_CONTROLMESSAGE_TYPE_PUBLISHREL  = 0x60
MQTT_CONTROLMESSAGE_TYPE_PUBLISHCOM  = 0x70
MQTT_CONTROLMESSAGE_TYPE_SUBSCRIBE   = 0x80
MQTT_CONTROLMESSAGE_TYPE_SUBSCRIBEACK= 0x90
MQTT_CONTROLMESSAGE_TYPE_PINGREQ     = 0xC0
MQTT_CONTROLMESSAGE_TYPE_PINGRES     = 0xD0
MQTT_CONTROLMESSAGE_TYPE_DISCONNECT  = 0xE0
MQTT_CONTROLMESSAGE_TYPE_QoS1        = 0x02
MQTT_CONTROLMESSAGE_TYPE_QoS2        = 0x04
MQTT_CONTROLMESSAGE_TYPE_NONE        = 0x00

MQTT_ControlMessage_Type = {
    MQTT_CONTROLMESSAGE_TYPE_CONNECT       :"MQTT_CONTROLMESSAGE_TYPE_CONNECT",
    MQTT_CONTROLMESSAGE_TYPE_CONNECTACK    :"MQTT_CONTROLMESSAGE_TYPE_CONNECTACK",
    MQTT_CONTROLMESSAGE_TYPE_PUBLISH       :"MQTT_CONTROLMESSAGE_TYPE_PUBLISH",
    MQTT_CONTROLMESSAGE_TYPE_PUBLISHACK    :"MQTT_CONTROLMESSAGE_TYPE_PUBLISHACK",
    MQTT_CONTROLMESSAGE_TYPE_PUBLISHRCV    :"MQTT_CONTROLMESSAGE_TYPE_PUBLISHRCV",
    MQTT_CONTROLMESSAGE_TYPE_PUBLISHREL    :"MQTT_CONTROLMESSAGE_TYPE_PUBLISHREL",
    MQTT_CONTROLMESSAGE_TYPE_PUBLISHCOM    :"MQTT_CONTROLMESSAGE_TYPE_PUBLISHCOM",
    MQTT_CONTROLMESSAGE_TYPE_SUBSCRIBE     :"MQTT_CONTROLMESSAGE_TYPE_SUBSCRIBE",
    MQTT_CONTROLMESSAGE_TYPE_SUBSCRIBEACK  :"MQTT_CONTROLMESSAGE_TYPE_SUBSCRIBEACK",
    MQTT_CONTROLMESSAGE_TYPE_PINGREQ       :"MQTT_CONTROLMESSAGE_TYPE_PINGREQ",
    MQTT_CONTROLMESSAGE_TYPE_PINGRES       :"MQTT_CONTROLMESSAGE_TYPE_PINGRES",
    MQTT_CONTROLMESSAGE_TYPE_DISCONNECT    :"MQTT_CONTROLMESSAGE_TYPE_DISCONNECT",
    MQTT_CONTROLMESSAGE_TYPE_QoS1	       :"MQTT_CONTROLMESSAGE_TYPE_QoS1",
    MQTT_CONTROLMESSAGE_TYPE_QoS2          :"MQTT_CONTROLMESSAGE_TYPE_QoS2",
    MQTT_CONTROLMESSAGE_TYPE_NONE          :"MQTT_CONTROLMESSAGE_TYPE_NONE",
}

# Connect Flags
CONNECT_USERNAME           = 0x80
CONNECT_PASSWORD           = 0x40
CONNECT_WILL               = 0x04
CONNECT_NONE		   = 0x00

MQTT_Connect_Flags = {
    CONNECT_USERNAME           :'CONNECT_USERNAME',
    CONNECT_PASSWORD           :'CONNECT_PASSWORD',
    CONNECT_WILL	           :'CONNECT_WILL',
    CONNECT_NONE		   :'CONNECT_NONE',
}


#MQTT Version 3.1.1 OASIS Standard (29 October 2014)
# http://docs.oasis-open.org/mqtt/mqtt/v3.1.1/os/mqtt-v3.1.1-os.pdf

class MQTT_ControlMessage_Type(Packet):
    name="MQTT Control Message"
    fields_desc =[
        XByteEnumField("ControlPacketType", 0x00, MQTT_ControlMessage_Type),
    ]

class MQTT_Connect(Packet):
    name="MQTT Connect"
    controlmessage_type = MQTT_CONTROLMESSAGE_TYPE_CONNECT
    fields_desc =[
        ByteField("HeaderFlags",0x00),
        ByteField("MessageLength",0x00),
        FieldLenField("ProtocolNameLength",None, fmt='H', length_of="ProtocolName"),
        StrFixedLenField("ProtocolName", "", 6),
        ByteField("Version",0x00),
        FlagsField("ConnectFlags", 0x00, -8, MQTT_Connect_Flags),
        XShortField("KeepAlive",0),
        FieldLenField("ClientIDLength",None, fmt='H', length_of="ClientID"),
        StrLenField("ClientID",b"",length_from=lambda x:x.ClientIDLength),
        ConditionalField(FieldLenField("WillTopicLength",None, fmt='H',length_of="WillTopic"), lambda x: x.ConnectFlags & CONNECT_WILL),
        ConditionalField(StrLenField("WillTopic", b'',length_from=lambda x: x.WillTopicLength), lambda x: x.ConnectFlags & CONNECT_WILL),
        ConditionalField(FieldLenField("WillMessageLength",None, fmt='H',length_of="WillMessage"), lambda x: x.ConnectFlags & CONNECT_WILL),
        ConditionalField(StrLenField("WillMessage", b'',length_from=lambda x: x.WillMessageLength), lambda x: x.ConnectFlags & CONNECT_WILL),

        ConditionalField(FieldLenField("UsernameLength",None, fmt='H',length_of="Username"), lambda x: x.ConnectFlags & CONNECT_USERNAME),
        ConditionalField(StrLenField("Username", b'',length_from=lambda x: x.UsernameLength), lambda x: x.ConnectFlags & CONNECT_USERNAME),
        ConditionalField(FieldLenField("PasswordLength",None, fmt='H',length_of="Password"), lambda x: x.ConnectFlags & CONNECT_PASSWORD),
        ConditionalField(StrLenField("Password", b'',length_from=lambda x: x.PasswordLength), lambda x: x.ConnectFlags & CONNECT_PASSWORD),
    ]

class MQTT_ConnectACK(Packet):
    name="MQTT Connect ACK"
    controlmessage_type = MQTT_CONTROLMESSAGE_TYPE_CONNECTACK
    fields_desc =[
        ByteField("HeaderFlags",0x20),
        ByteField("MessageLength",0x02),
        XShortField("ConnectionACK",0x00)
    ]

class MQTT_Publish(Packet):
    name="MQTT Publish"
    controlmessage_type = MQTT_CONTROLMESSAGE_TYPE_PUBLISH
    fields_desc =[
        ByteField("HeaderFlags",0x00),
        ByteField("MessageLength",0x00),
        FieldLenField("TopicLength",None, fmt='H', length_of="Topic"),
        StrLenField("Topic",b"",length_from=lambda x:x.TopicLength),
        ConditionalField(XShortField("PacketIdentifier",0), lambda x: x.HeaderFlags & (MQTT_CONTROLMESSAGE_TYPE_QoS1 | MQTT_CONTROLMESSAGE_TYPE_QoS2)),
        StrLenField("Message",b"",length_from=lambda x:x.MessageLength-x.TopicLength-2)
    ]

class MQTT_PublishACK(Packet):
    name="MQTT PUBLISH ACK"
    controlmessage_type = MQTT_CONTROLMESSAGE_TYPE_CONNECTACK
    fields_desc =[
        ByteField("HeaderFlags",0x40),
        ByteField("MessageLength",0x02),
        XShortField("ConnectionACK",0x00),
    ]

class MQTT_PublishACK_Identifier(Packet):
    name="MQTT PUBLISH ACK Identifier"
    controlmessage_type = MQTT_CONTROLMESSAGE_TYPE_CONNECTACK
    fields_desc =[
        ByteField("HeaderFlags",0x40),
        ByteField("MessageLength",0x02),
        XShortField("PacketIdentifier",0x00),
    ]

class MQTT_Publish_Release(Packet):
    name="MQTT PUBLISH Release"
    controlmessage_type = MQTT_CONTROLMESSAGE_TYPE_PUBLISHREL
    fields_desc =[
        ByteField("HeaderFlags",0x00),
        ByteField("MessageLength",0x00),
        XShortField("PacketIdentifier",0x00),
    ]

class MQTT_Subscribe(Packet):
    name="MQTT Subscribe"
    controlmessage_type = MQTT_CONTROLMESSAGE_TYPE_SUBSCRIBE
    fields_desc =[
        ByteField("HeaderFlags",0x00),
        ByteField("MessageLength",0x00),
        ConditionalField(XShortField("PacketIdentifier",0), lambda x: x.HeaderFlags & (MQTT_CONTROLMESSAGE_TYPE_QoS1 | MQTT_CONTROLMESSAGE_TYPE_QoS2)),
        FieldLenField("TopicLength",None, fmt='H', length_of="Topic"),
        StrLenField("Topic",b"",length_from=lambda x:x.TopicLength),
        ByteField("GrantedQoS",0x00),
    ]

class MQTT_SubscribeACK(Packet):
    name="MQTT Subscribe ACK"
    controlmessage_type = MQTT_CONTROLMESSAGE_TYPE_SUBSCRIBEACK
    fields_desc =[
        ByteField("HeaderFlags",0x90),
        ByteField("MessageLength",0x02),
        ByteField("GrantedQoS",0x00),
    ]

class MQTT_SubscribeACK_Identifier(Packet):
    name="MQTT Subscribe ACK Identifier"
    controlmessage_type = MQTT_CONTROLMESSAGE_TYPE_SUBSCRIBEACK
    fields_desc =[
        ByteField("HeaderFlags",0x90),
        ByteField("MessageLength",0x02),
        XShortField("PacketIdentifier",0x00),
        ByteField("GrantedQoS",0x00),
    ]

class MQTT_PingRequest(Packet):
    name="MQTT Ping Request"
    controlmessage_type = MQTT_CONTROLMESSAGE_TYPE_PINGREQ
    fields_desc =[
        ByteField("HeaderFlags",0x00),
        ByteField("MessageLength",0x00),
    ]

class MQTT_PingResponse(Packet):
    name="MQTT Ping Response"
    controlmessage_type = MQTT_CONTROLMESSAGE_TYPE_PINGRES
    fields_desc =[
        ByteField("HeaderFlags",0xd0),
        ByteField("MessageLength",0x00),
    ]

class MQTT_DisconnectReq(Packet):
    name="MQTT Disconnect Request"
    controlmessage_type = MQTT_CONTROLMESSAGE_TYPE_DISCONNECT
    fields_desc =[
        ByteField("HeaderFlags",0x00),
        ByteField("MessageLength",0x00),
    ]
