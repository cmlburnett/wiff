from bstruct import *

class chunk_struct(metaclass=bstructmeta):
	dat = {
		'magic': member_str(0, 8),
		'size': member_8(8),
		'attributes': member_8(16),
	}

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
		'name': member_str('index_name_start', 'index_name_end'),
	}
	@staticmethod
	def lenplan(name):
		ret = 21

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
		ret = 28

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

