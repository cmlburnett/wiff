"""
This file contains the struct definitions.
This is the de facto definition of the file formats: what is defined here is WHAT the files should be.
Other documentation is secondary to what is written here (hopefully they agree).

These structs are defined using a custom binary struct (bstruct) library I wrote to handle this.
The goal is to avoid application caching of data and so the bstruct layer uses mmap()'ed files
 to read/write file data.
Thus, modifying members of these structs gets directly reflected in the binary data in the file.
The key challenge with this is handling offsets correctly which necessitating writing that logic
 in a separate library (one-off errors would be catastrophic).

Polymorphism is used on the annotation types using the @type member.
Calling condition_on('type') will return the correct struct type depending on the @type value.
"""

from bstruct import *

import enum

class chunk_struct(metaclass=bstructmeta):
	"""
	A chunk is a 24 byte header with arbitrary binary data after it.
	This layout is inspired from the EA IFF 85 except this is 64-bit size where as IFF is 32-bit.
	This also adds an 8 byte array of attributes that can change how the binary data blob is interpreted.

	@magic is an 8 character ASCII string of WIFFINFO, WIFFWAVE, or WIFFANNO.
	@size is a 64-bit size of the chunk
	@attributes is an 8 byte array of data that changes with each chunk type

	The main structs are info_struct, annos_struct, and wave_struct.
	"""
	dat = {
		'magic': member_str(0, 8),
		'size': member_8I(8),
		'attributes': member_8I(16),
	}
	@staticmethod
	def lenplan(size):
		# Size is the whole chunk, nothing difficult here
		return size

class channel_struct(metaclass=bstructmeta):
	"""
	Sub-struct to handle individual channel definitions.
	"""
	dat = {
		'index': member_1I(0),
		'index_name': member_ref(1),
		'bit': member_1I(3),
		'index_unit': member_ref(4),
		'index_comment_start': member_ref(6),
		'index_comment_end': member_ref(8),
		'name': member_str('index_name', 'index_unit'),
		'unit': member_str('index_unit', 'index_comment_start'),
		'comment': member_str('index_comment_start', 'index_comment_end'),
	}
	@staticmethod
	def lenplan(name, unit, comment):
		ret = 10

		for v in [name, unit, comment]:
			if isinstance(v, str):
				ret += len(v.encode('utf8'))
			elif isinstance(v, bytes):
				ret += len(v)
			else:
				raise TypeError("Cannot handle type '%s'" % (str(type(v)),))

		return ret

class file_struct(metaclass=bstructmeta):
	"""
	Sub-struct to handle individual file definitions.
	"""
	dat = {
		'index': member_1I(0),
		'index_name_start': member_ref(1),
		'index_name_end': member_ref(3),
		'fidx_start': member_8I(5),
		'fidx_end': member_8I(13),
		'aidx_start': member_8I(21),
		'aidx_end': member_8I(29),
		'name': member_str('index_name_start', 'index_name_end'),
	}
	@staticmethod
	def lenplan(name):
		ret = 37

		for v in [name]:
			if isinstance(v, str):
				ret += len(v.encode('utf8'))
			elif isinstance(v, bytes):
				ret += len(v)
			else:
				raise TypeError("Cannot handle type '%s'" % (str(type(v)),))

		return ret

class info_struct(metaclass=bstructmeta):
	"""
	Main struct for WIFFINFO chunk.
	Uses a jump table and list to manage the channels and files.
	This is the first chunk in the primary file.
	"""
	dat = {
		'index_start': member_ref(0),
		'index_end': member_ref(2),
		'index_description': member_ref(4),
		'index_channels': member_ref(6),
		'index_file_start': member_ref(8),
		'index_file_end': member_ref(10),
		'fs': member_4I(12),
		'num_channels': member_2I(16),
		'num_files': member_2I(18),
		'num_frames': member_8I(20),
		'num_annotations': member_8I(28),
		'num_metas': member_8I(36),
		'start': member_str('index_start', 'index_end'),
		'end': member_str('index_end', 'index_description'),
		'description': member_str('index_description', 'index_channels'),
		'channels_jumptable': member_jumptable('index_channels', 'num_channels', 'channels'),
		'channels': member_list(channel_struct, 'channels_jumptable'),
		'files_jumptable': member_jumptable('index_file_start', 'num_files', 'files'),
		'files': member_list(file_struct, 'files_jumptable'),
	}
	@staticmethod
	def lenplan(start, end, description, chans, files):
		# Should match num_frames offset + 8
		ret = 44

		for v in [start, end, description]:
			if isinstance(v, str):
				ret += len(v.encode('utf8'))
			elif isinstance(v, bytes):
				ret += len(v)
			else:
				raise TypeError("Cannot handle type '%s'" % (str(type(v)),))

		# Include jumptable size
		ret += len(chans) * 4
		for chan in chans:
			ret += channel_struct.lenplan(*chan)

		# Iinclude jumptable size
		ret += len(files) * 4
		for f in files:
			ret += file_struct.lenplan(*f)

		return ret

class wave_struct(metaclass=bstructmeta):
	"""
	WIFFWAVE struct that defines a segment of frames of binary data.
	Each segment defines which channels it includes, which is necessary to know how to interpret the data.

	@channels is a 32 byte binary blob of 256 bits where each bit of 1 indicates the channel is included and 0 indicates the channel is NOT included
	@fidx_start is the first frame (absolute) index contained in this segment
	@fidx_end is the last frame (absolute) index contained in this segment
	@records is a binary blob (after the channel data is understood, the record size is manually set at run time to appropriate parse individual records from this blob
	"""
	dat = {
		'channels': member_binary(0),
		'fidx_start': member_8I(32),
		'fidx_end': member_8I(40),
		# Size of the record set to 1 to have something set, it should be adjusted
		# based on runtime needs
		'records': member_binary_record(48, 1),
	}
	@staticmethod
	def lenplan(record_size, num_records):
		return 48 + record_size+num_records

class ann_C_struct(metaclass=bstructmeta):
	"""
	A "C" annotation which is just a UTF8 comment.

	@type is "C" to indicate a comment annotation
	@fidx_start is the starting frame (absolute) index this annotation is marking up
	@fidx_end is the ending frame (absolute) index this annotation is marking up (if equal to start, this annotation applies to a single frame)
	@index_comment_start is the relative index of the start of the comment string
	@index_comment_end is the relative index of the end of the comment string
	@comment is the UTF-8 encoded comment string
	"""
	dat = {
		'type': member_1I(0),
		'fidx_start': member_8I(1),
		'fidx_end': member_8I(9),
		'index_comment_start': member_ref(17),
		'index_comment_end': member_ref(19),
		'comment': member_str('index_comment_start', 'index_comment_end'),
	}
	@staticmethod
	def lenplan(comment):
		ret = 21

		for v in [comment]:
			if isinstance(v, str):
				ret += len(v.encode('utf8'))
			elif isinstance(v, bytes):
				ret += len(v)
			else:
				raise TypeError("Cannot handle type '%s'" % (str(type(v)),))

		return ret

class ann_M_struct(metaclass=bstructmeta):
	"""
	A "M" annotation is a simple marker that consists of a 32-bit value.

	@type is "M" to indicate a marker annotation
	@fidx_start is the starting frame (absolute) index this annotation is marking up
	@fidx_end is the ending frame (absolute) index this annotation is marking up (if equal to start, this annotation applies to a single frame)
	@marker is a 32-bit value marker that is defined by the application layer (can be a number, or a 4-character ASCII string stored as a 32-bit number)
	"""
	dat = {
		'type': member_1I(0),
		'fidx_start': member_8I(1),
		'fidx_end': member_8I(9),
		'marker': member_4I(17),
	}
	@staticmethod
	def lenplan():
		return 21

class ann_D_struct(metaclass=bstructmeta):
	"""
	A "D" annotation is a marker that consists of a 32-bit value and a 64-bit value.
	The value could be an interpreted value from the data contained witin the indicated frames (eg, a QRS interval in miliseconds stroed as a 64-bit float).

	@type is "D" to indicate a marker annotation
	@fidx_start is the starting frame (absolute) index this annotation is marking up
	@fidx_end is the ending frame (absolute) index this annotation is marking up (if equal to start, this annotation applies to a single frame)
	@marker is a 32-bit value marker that is defined by the application layer (can be a number, or a 4-character ASCII string stored as a 32-bit number)
	@value is a 64-bit value defined by the application layer (can be a 64-bit integer, two 32-bit integers, a 64-bit float, or......)
	"""
	dat = {
		'type': member_1I(0),
		'fidx_start': member_8I(1),
		'fidx_end': member_8I(9),
		'marker': member_4I(17),
		'value': member_8I(21),
	}
	@staticmethod
	def lenplan():
		return 29

class ann_struct(metaclass=bstructmeta):
	"""
	An annotation consists of a type, frame interval, and data.
	Annotations are polymorphic on the @type member and are defined as above.
	"""
	dat = {
		'type': member_str(0, 1),
		'fidx_start': member_8I(1),
		'fidx_end': member_8I(9),
		'data': member_binary(17),
	}
	conditional = {
		'type': {
			'C': ann_C_struct,
			'M': ann_M_struct,
			'D': ann_D_struct
		}
	}
	@staticmethod
	def lenplan(typ, **kargs):
		if typ == '\0':
			# Null annotation
			return 17
		elif typ == 'C':
			return ann_C_struct.lenplan(kargs['comment'])
		elif typ == 'D':
			return ann_D_struct.lenplan()
		elif typ == 'M':
			return ann_M_struct.lenplan()
		else:
			raise ValueError("Unrecognized annotation type '%s'" % typ)

class annos_struct(metaclass=bstructmeta):
	"""
	WIFFANNO struct that defines a list of annotations marking up the WIFFWAVE frames of data.
	Each annotation applies to a single frame, or an interval of frames, and includes some sort of data.
	This struct defines the minimu and maximum frame (absolute) index and annotation (absolute) index included in this segment.

	@aidx_start is the starting annotation (absolute) index in this chunk
	@aidx_end is the last annotation (absolute) index in this chunk
	@fidx_first is the first referenced frame (absolute) index of all annotations in this chunk
	@fidx_last is the last referenced frame (absolute) index of all annotations in this chunk
	@num_annotations is the number of annotations in this chunk
	@index_annotations is the (relative) index of the annotations list
	@annotations_jumptable is the jumptable for the annotations list
	@annotations is the list of annotations (polymorphic ann_struct)
	"""
	dat = {
		'aidx_start': member_8I(0),
		'aidx_end': member_8I(8),
		'fidx_first': member_8I(16),
		'fidx_last': member_8I(24),
		'num_annotations': member_4I(32),
		'index_annotations': member_ref(36),
		'annotations_jumptable': member_jumptable('index_annotations', 'num_annotations', 'annotations'),
		'annotations': member_list(ann_struct, 'annotations_jumptable'),
	}
	@staticmethod
	def lenplan(annos):
		ret = 36
		ln = len(annotations)

		ret += ln * 4
		d,r = divmod(ret, 4096)
		if r != 0:
			d += 1

		# Round to the nearest page
		ret = d * 4096

		# Sum up the annotations
		z = sum([ann_struct(_) for _ in annos])
		d,r = divmod(z, 4096)
		if r != 0:
			d += 1

		# Round annotations to the nearest page
		ret += d *4096

		return ret

class meta_data_1I_struct(metaclass=bstructmeta):
	dat = {
		'num_data': member_2I(0),
		'data': member_1I_array(2),
	}
	@staticmethod
	def lenplan(ln):
		return 2 + 1*ln

class meta_data_2I_struct(metaclass=bstructmeta):
	dat = {
		'num_data': member_2I(0),
		'data': member_2I_array(2),
	}
	@staticmethod
	def lenplan(ln):
		return 2 + 2*ln

class meta_data_4I_struct(metaclass=bstructmeta):
	dat = {
		'num_data': member_2I(0),
		'data': member_4I_array(2),
	}
	@staticmethod
	def lenplan(ln):
		return 2 + 4*ln

class meta_data_8I_struct(metaclass=bstructmeta):
	dat = {
		'num_data': member_2I(0),
		'data': member_8I_array(2),
	}
	@staticmethod
	def lenplan(ln):
		return 2 + 8*ln

class meta_data_4F_struct(metaclass=bstructmeta):
	dat = {
		'num_data': member_2I(0),
		'data': member_4F_array(2),
	}
	@staticmethod
	def lenplan(ln):
		return 2 + 4*ln

class meta_data_8F_struct(metaclass=bstructmeta):
	dat = {
		'num_data': member_2I(0),
		'data': member_8F_array(2),
	}
	@staticmethod
	def lenplan(ln):
		return 2 + 8*ln

class meta_str_struct(metaclass=bstructmeta):
	dat = {
		'index_start': member_ref(0),
		'index_end': member_ref(2),
		'str': member_str('index_start','index_end'),
	}
	@staticmethod
	def lenplan(s):
		return 4 + len(s.encode('utf8'))

class meta_data_str_struct(metaclass=bstructmeta):
	"""

	@subtype is intended to be a MIME type to indicate how string data should be interpreted (eg, string, XML, JSON)
	"""
	dat = {
		'type': member_1I(0),
		'subtype': member_1I(1),
		'num_strings': member_2I(2),
		'strings_jumptable': member_jumptable(4, 'num_strings', 'strings' ),
		'strings': member_list('strings_jumptable', meta_str_struct),
	}
	@staticmethod
	def lenplan(strs):
		ret = 2

		ret += 4 * len(strs)
		ret += sum([len(_) for _ in strs])
		return ret

class meta_data_struct(metaclass=bstructmeta):
	dat = {
		'type': member_1I(0),
		'data': member_binary(1),
	}
	conditional = {
		'type': {
			0: meta_data_str_struct,
			1: meta_data_1I_struct,
			2: meta_data_2I_struct,
			3: meta_data_4I_struct,
			4: meta_data_8I_struct,
			5: meta_data_4F_struct,
			6: meta_data_8F_struct,
		},
	}
	@staticmethod
	def lenplan(typ, data):
		if typ == 0: return meta_data_str_struct.lenplan(data)
		elif typ == 1: return meta_data_1I_struct.lenplan(len(data))
		elif typ == 2: return meta_data_2I_struct.lenplan(len(data))
		elif typ == 3: return meta_data_4I_struct.lenplan(len(data))
		elif typ == 4: return meta_data_8I_struct.lenplan(len(data))
		elif typ == 5: return meta_data_4F_struct.lenplan(len(data))
		elif typ == 6: return meta_data_8F_struct.lenplan(len(data))
		else:
			raise ValueError("Unrecognized type %d" % typ)

class meta_struct(metaclass=bstructmeta):
	"""
	Metadata value.
	Levels:
		0 -- Recording level information (index has no meaning here)
		1 -- Channel
		2 -- File
		3 -- Frame
		4 -- Annotation
		5 -- Meta (meta about meta, how meta is that?)
	For some of these, the @level_index indicates which specific entry the value applies to

	Types (all are assuming to be a list of the same type:
		0 -- String
		1 -- 8-bit int
		2 -- 16-bit int
		3 -- 32-bit int
		4 -- 64-bit int
		5 -- 32-bit float
		6 -- 64-bit float

	The keys are always UTF-8 strings.
	The format of the keys are up to the application and can be flat keys, or nested keys using a delimiter (eg, period, colon, slash)
	 or any other structure as desired.
	Overall, the keys must be unique and no duplicates permitted.

	@index_key_start is the starting (relative) offset of the start of the key string
	@index_key_end is the ending (relative) offset of the end of the key string
	@index_data_start is the starting (relative) offset of the binary data for this value
	@index_data_end is the ending (relative) offset of the binary data for this value
	@level is an integer describing which aspect of this recording this metadata value applies to
	@level_index is the index that may be relavent to the @level
	@key is the application defined key that defines what this metadata value is all about
	@data is a sub struct that is polymorphic
	"""
	dat = {
		'index_key_start': member_ref(0),
		'index_key_end': member_ref(2),
		'index_data_start': member_ref(4),
		'index_data_end': member_ref(6),
		'level': member_1I(7),
		'level_index': member_8I(8),
		'key': member_str('index_key_start', 'index_key_end'),
		'data': member_substruct('index_data_start', meta_data_struct),
	}
	@staticmethod
	def lenplan(key, data_type, data):
		"""
		For planning, @data must always be a list or tuple.
		Passing a singular value is not accepted at this level.
		"""

		return 16 + len(key) + meta_data_struct.lenplan(data_type, data)

class metas_struct(metaclass=bstructmeta):
	"""
	WIFFMETA struct that defines metadata about the entire recording.
	"""
	dat = {
		'num_metas': member_4I(0),
		'index_metas': member_ref(4),
		'metas_jumptable': member_jumptable('index_metas', 'num_metas', 'metas'),
		'metas': member_list(meta_struct, 'metas_jumptable'),
	}

	class LEVEL(enum.Enum):
		"""Enum listing the known levels."""
		RECORDING = 0
		CHANNEL = 1
		FILE = 2
		FRAME = 3
		ANNOTATION = 4
		META = 5

	class TYPE(enum.IntEnum):
		"""Enum listing the known meta value types."""
		STRING = 0
		INT8 = 1
		INT16 = 2
		INT32 = 3
		INT64 = 4
		FLOAT32 = 5
		FLOAT64 = 6

	@classmethod
	def level_to_string(cls, val):
		return cls.LEVEL(val).name
	@classmethod
	def level_from_string(cls, val):
		return cls.LEVEL[val.upper()].value

	@classmethod
	def type_to_string(cls, val):
		return cls.TYPE(val).name
	@classmethod
	def type_from_string(cls, val):
		return cls.TYPE[val].value

