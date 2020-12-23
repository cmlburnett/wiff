
import struct

import bstruct

from .bits import bitfield
from .wiffchunk import WIFF_chunk
from .structs import metas_struct, meta_struct, meta_data_struct

class WIFFMETA:
	"""
	Helper class that handles meta values.
	"""

	def __init__(self, wiff, fw, chunk):
		self.wiff = wiff
		self.fw = fw
		self.chunk = chunk
		self._s = metas_struct(fw, chunk.data_offset)

	def initchunk(self, compression):
		"""
		Initiailizes a new chunk for this chunk type.
		"""

		# All new chunks are given a 4096 block initially
		# Expand to 2 blocks (1 for jumptable, 1 for data)
		self.fw.resize_add(4096)

		self.chunk.magic = 'WIFFMETA'
		self.chunk.size = 4096*2
		self.chunk.attributes = (0,0,0,0, 0,0,0,0)

		attrs = [0]*8
		if compression is None:
			attrs[0] = ord('0')
		elif compression.lower() == 'z':
			attrs[0] = ord('Z')
		elif compression.lower() == 'b':
			attrs[0] = ord('B')
		else:
			raise ValueError('Unrecognized comppression type "%s"' % compression)

		self.chunk.attributes = tuple(attrs)

	def initheader(self):
		"""
		Initialize a new header
		"""

		self.num_metas = 0
		self.index_metas = 6

	@property
	def num_metas(self): return self._s.num_metas.val
	@num_metas.setter
	def num_metas(self, val): self._s.num_metas.val = val

	@property
	def metas(self): return self._s.metas

	@staticmethod
	def guess_type(data):
		"""
		Based on @data, return a metas_struct.TYPE enum value that best fits the data.
		Floats are always assumed to be 64-bit.
		Integers are boxed to the 1, 2, 4, or 8 byte values based on the numbers presented.
		"""

		# Values are a list or tuple, so have to check consistency amongst the items
		if isinstance(data, list) or isinstance(data, tuple):
			ts = [type(_) for _ in data]
			x0 = ts[0]
			if not all([x0 == _ for _ in ts[1:]]):
				raise TypeError('Data type is not the same for all items')

			if x0 == int:
				mn = min(data)
				mx = max(data)

				if mx < 2**7 and mn >= -2**7:
					return metas_struct.TYPE.INT8
				elif mx < 2**15 and mn >= -2**15:
					return metas_struct.TYPE.INT16
				elif mx < 2**31 and mn >= -2**31:
					return metas_struct.TYPE.INT32
				elif mx < 2**63 and mn >= -2**63:
					return metas_struct.TYPE.INT64
				else:
					raise ValueError("Integers are too big to fit in 64-bit values")
			elif x0 == float:
				# Assume double floats...
				return metas_struct.TYPE_FLOAT64
			elif x0 == str:
				return metas_struct.TYPE_STRING
			else:
				raise TypeError("Unrecognized data type: %s" % (x0,))


		# Only a single value, much easier
		elif isinstance(data, int):
			if data < 2**7 and data >= -2**7:
				return metas_struct.TYPE.INT8
			elif data < 2**15 and data >= -2**15:
				return metas_struct.TYPE.INT16
			elif data < 2**31 and data >= -2**31:
				return metas_struct.TYPE.INT32
			elif data < 2**63 and data >= -2**63:
				return metas_struct.TYPE.INT64
			else:
				raise ValueError("Integers are too big to fit in 64-bit values")
		elif isinstance(data, float):
			return metas_struct.TYPE.FLOAT64
		elif isinstance(data, str):
			return metas_struct.TYPE.STRING

		# Not a supported type otherwise
		else:
			raise TypeError("Cannot guess type from %s" % (type(data),))

	def add_meta(self, level, level_index, key, data, data_type=None):
		"""
		Add a new meta value to this chunk.
		@level describes which abstract level this value applies to (the recording, channel, frame, etc).
		@level_index picks the particular item out of items at the particular level.
		@key is a string representing the key/value pair for this meta value.
		@data is a single or list/tuple of items of the same data type for thie meta value.
		@data_type is an enum value (metas_struct.TYPE) indicating how the data is encoded into the chunk. If None, then the type is inferred from the values.
		"""

		# Convert from string
		if isinstance(level, str):
			level = metas_struct.level_from_string(level)
		elif isinstance(level, int):
			level = metas_struct.LEVEL(level)
		elif isinstance(level, metas_struct.LEVEL):
			pass
		else:	
			raise TypeError("Level is unknown type, cannot convert it: %s" % (level,))

		# Ignore index when applying to recording level (0)
		if level == metas_struct.LEVEL.RECORDING:
			level_index = 0

		# Ensure key is a string
		if not isinstance(key, str):
			raise ValueError("Key must be a string, got %s" % type(key))

		if data_type is None:
			data_type = WIFFMETA.guess_type(data)
		else:
			# Ensure correct type of the value
			if not isinstance(data_type, metas_struct.TYPE):
				raise TypeError("data_type must be a %s, got %s" % (metas_struct.TYPE, type(data_type)))

		# Wrap in tuple if not already
		if isinstance(data, list) or isinstance(data, tuple):
			pass
		else:
			data = tuple(data)


		# Convert string to utf8
		key = key.encode('utf-8')
		if isinstance(data[0], str):
			data = [_.encode('utf-8') for _ in data]


		# Get length of meta value
		ln = meta_struct.lenplan(key, data_type.value, data)
		kln = len(key)
		dln = meta_data_struct.lenplan(data_type.value, data)

		# Add to jump table
		print([ln, 4096-self._s.metas_jumptable.offset-self.chunk.len])
		m_no = self._s.metas.add(ln, start=4096-self._s.metas_jumptable.offset-self.chunk.len, page=4096)

		# Access meta_struct
		print(['m_no', m_no, ln, kln, dln])
		return
		raise Exception()
		m = self._s.metas[m_no]
		m.index_key_start.val = 16
		m.index_key_end.val = 16 + kln
		m.index_value_start.val = 16 + kln
		m.index_value_end.val = 16 + kln + dln


