
import os
import struct

from .structs import chunk_struct

class WIFF_chunk:
	"""
	Helper class to interface with chunk headers.
	"""
	def __init__(self, fw, offset):
		self._s = chunk_struct(fw, offset)

	def resize_callback(self, sz):
		self.size = sz

	@property
	def offset(self): return self._s.offset

	@property
	def data_offset(self): return self.offset + self.len

	@property
	def magic(self): return self._s.magic.val
	@magic.setter
	def magic(self, v): self._s.magic.val = v

	@property
	def size(self): return self._s.size.val
	@size.setter
	def size(self, v): self._s.size.val = v

	@property
	def len(self): return 24

	@property
	def attributes(self):
		return struct.unpack("<BBBBBBBB", struct.pack("<Q", self._s.attributes.val))
	@attributes.setter
	def attributes(self, v):
		self._s.attributes.val = struct.unpack("<Q", struct.pack("<BBBBBBBB", *v))[0]


	@staticmethod
	def FindChunks(f):
		total_sz = os.path.getsize(f.name)

		chunks = []

		off = 0
		while off < total_sz:
			f.seek(off)

			p = {
				'magic': f.read(8).decode('utf8'),
				'size': None,
				'attrs': None,
			}

			dat = f.read(8)
			sz = struct.unpack("<Q", dat)[0]
			if sz == 0:
				raise ValueError("Found zero length chunk, non-sensical")
			p['size'] = sz

			dat = f.read(8)
			p['attrs'] = struct.unpack("<BBBBBBBB", dat)

			# Include offsets
			p['offset header'] = off
			p['offset data'] = off + 24

			chunks.append(p)
			off += p['size']

		return chunks

	@staticmethod
	def ResizeChunk(chk, new_size):
		"""
		Resize the chunk @chk to the new size indicated @new_size in bytes.
		If not the last chunk in the file, then everything after it must be moved
		"""

		# Work only in pages
		if new_size % 4096 != 0:
			raise ValueError("New size for a chunk must be in an increment of 4096: %d" % new_size)

		if chk.size == new_size:
			# NOP: done already...
			return
		elif chk.size > new_size:
			raise ValueError("Cannot shrink chunk size (currently %d, requested %d)" % (cur, val))

		# Current file size in bytes
		fsize = os.path.getsize(chk._s.fw.fname)

		# Size to increment by
		delta = new_size - chk.size

		# Get in pages
		## Start is the page start of this chunk
		pg_chk_start = chk.offset // 4096
		## Page offset of the page after the end of this chunk
		pg_chk_end = (chk.offset + chk.size) // 4096
		## Total size in pages
		pg_total = fsize // 4096

		# Increase file size
		chk._s.fw.resize_add(delta)

		# If not the last chunk, then need to move pages
		if fsize > chk.offset + chk.size:
			# Have to iterate backward overwise pages could overwrite
			# If moving pages 3 & 4 (eg, range(3,5)) then have to iterate 4 then 3 (eg, range(5-1,4-1,-1)
			for i in range(pg_total-1, pg_chk_end-1, -1):
				# Old offset is the start of the page
				of_old = i*4096
				# New offset is the delta of the new pages
				of_new = i*4096 + delta
				# Move the page
				chk._s.fw[of_new:of_new+4096] = chk._s.fw[of_old:of_old+4096]
		else:
			# Chunk at end; nothing to move (just expand the chunk and file at the end)
			pass

		for i in range(pg_chk_end, pg_chk_end+(delta//4096)):
			# Blank the now vacant page (strictly not necessary as data within a chunk shouldn't be parsed
			# but blank it anyway for good measure)
			chk._s.fw[i*4096:(i+1)*4096] = b'\0'*4096

		# Record the chunk size as bigger
		chk.size = new_size
