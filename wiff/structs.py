from bstruct import *

class chunk_struct(metaclass=bstructmeta):
	dat = {
		'magic': member_str(0, 8),
		'size': member_8(8),
		'attributes': member_8(16),
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
		'index': member_1(0),
		'index_name': member_ref(1),
		'bit': member_1(3),
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
		'index': member_1(0),
		'index_name_start': member_ref(1),
		'index_name_end': member_ref(3),
		'fidx_start': member_8(5),
		'fidx_end': member_8(13),
		'aidx_start': member_8(21),
		'aidx_end': member_8(29),
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
	"""
	dat = {
		'index_start': member_ref(0),
		'index_end': member_ref(2),
		'index_description': member_ref(4),
		'index_channels': member_ref(6),
		'index_file_start': member_ref(8),
		'index_file_end': member_ref(10),
		'fs': member_4(12),
		'num_channels': member_2(16),
		'num_files': member_2(18),
		'num_frames': member_8(20),
		'num_annotations': member_8(28),
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
		ret = 36

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
	dat = {
		'channels': member_binary(0),
		'fidx_start': member_8(32),
		'fidx_end': member_8(40),
		# Size of the record set to 1 to have something set, it should be adjusted
		# based on runtime needs
		'records': member_binary_record(48, 1),
	}
	@staticmethod
	def lenplan(record_size, num_records):
		return 48 + record_size+num_records

class ann_C_struct(metaclass=bstructmeta):
	dat = {
		'type': member_1(0),
		'fidx_start': member_8(1),
		'fidx_end': member_8(9),
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
	dat = {
		'type': member_1(0),
		'fidx_start': member_8(1),
		'fidx_end': member_8(9),
		'marker': member_4(17),
	}
	@staticmethod
	def lenplan():
		return 21

class ann_D_struct(metaclass=bstructmeta):
	dat = {
		'type': member_1(0),
		'fidx_start': member_8(1),
		'fidx_end': member_8(9),
		'marker': member_4(17),
		'value': member_8(21),
	}
	@staticmethod
	def lenplan():
		return 29

class ann_struct(metaclass=bstructmeta):
	dat = {
		'type': member_str(0, 1),
		'fidx_start': member_8(1),
		'fidx_end': member_8(9),
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
	dat = {
		'aidx_start': member_8(0),
		'aidx_end': member_8(8),
		'fidx_first': member_8(16),
		'fidx_last': member_8(24),
		'num_annotations': member_4(32),
		'index_annotations': member_ref(36),
		'annotations_jumplist': member_jumptable('index_annotations', 'num_annotations', 'annotations'),
		'annotations': member_list(ann_struct, 'annotations_jumplist'),
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

