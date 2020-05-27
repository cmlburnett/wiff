
import struct

from .structs import annos_struct, ann_struct, ann_C_struct, ann_D_struct, ann_M_struct
from .util import twotuplecheck

class WIFFANNO:
	"""
	Helper class that handles annotations.
	"""

	def __init__(self, wiff, fw, chunk):
		self.wiff = wiff
		self.fw = fw
		self.chunk = chunk
		self._s = annos_struct(fw, chunk.data_offset)

	def initchunk(self, compression):
		"""
		Initiailizes a new chunk for this chunk type.
		"""

		# All new chunks are given a 4096 block initially
		# Expand to 2 blocks (1 for jumptable, 1 for data)
		self.fw.resize_add(4096)

		self.chunk.magic = 'WIFFANNO'
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
		Initialize a new header.
		"""

		self.aidx_start = 0
		self.aidx_end = 0
		self.fidx_first = 0
		self.fidx_last = 0
		self.num_annotations = 0
		self._s.index_annotations.val = 38

	@property
	def magic(self): return self.chunk.magic

	@property
	def aidx(self): return bstruct.interval(self.aidx_start, self.aidx_end)
	def fidx(self): return bstruct.interval(self.fidx_first, self.fidx_last)

	@property
	def aidx_start(self): return self._s.aidx_start.val
	@aidx_start.setter
	def aidx_start(self, val): self._s.aidx_start.val = val

	@property
	def aidx_end(self): return self._s.aidx_end.val
	@aidx_end.setter
	def aidx_end(self, val): self._s.aidx_end.val = val

	@property
	def fidx_first(self): return self._s.fidx_first.val
	@fidx_first.setter
	def fidx_first(self, val): self._s.fidx_first.val = val

	@property
	def fidx_last(self): return self._s.fidx_last.val
	@fidx_last.setter
	def fidx_last(self, val): self._s.fidx_last.val = val

	@property
	def num_annotations(self): return self._s.num_annotations.val
	@num_annotations.setter
	def num_annotations(self, val): self._s.num_annotations.val = val

	@property
	def annotations(self): return self._s.annotations


	def add_annotation_C(self, fidx, comment):
		return self.add_annotation('C', fidx, comment=comment)
	def add_annotation_M(self, fidx, marker):
		return self.add_annotation('M', fidx, marker=marker)
	def add_annotation_D(self, fidx, marker, value):
		return self.add_annotation('D', fidx, marker=marker, value=value)
	def add_annotation(self, typ, fidx, **parms):
		"""
		Adds an annotation to the currently selected annotation segment.
		Can use this generic function, or one of the related functions to simplify coding.
		"""

		# Check for annotation type
		if typ == 'C':
			if 'comment' not in parms: raise ValueError("For a 'C' annotation, expected a comment parameter")
		elif typ == 'M':
			if 'marker' not in parms: raise ValueError("For a 'M' annotation, expected a marker parameter")
		elif typ == 'D':
			if 'marker' not in parms: raise ValueError("For a 'D' annotation, expected a marker parameter")
			if 'value' not in parms: raise ValueError("For a 'D' annotation, expected a value parameter")
		else:
			raise KeyError("Unexpected annotation type '%s', not recognized" % (typ,))

		# Coerce if able to an interval
		fidx = twotuplecheck(fidx)

		ln = ann_struct.lenplan(typ, **parms)

		# Convert 4-char string to a 32-bit number
		if 'marker' in parms and isinstance(parms['marker'], str):
			parms['marker'] = struct.unpack("<I", parms['marker'].encode('ascii'))[0]

		# Get the annotation number (same as the annotations[] index)
		ann_no = self.num_annotations

		# Initialize these
		if self.num_annotations == 0:
			# First annotation
			self.aidx_start = 0
			self.aidx_end = 0
			self.fidx_first = fidx.start
			self.fidx_last = fidx.stop

		# Add to jump table
		self._s.annotations.add(ln, start=4096-self._s.annotations_jumplist.offset-self.chunk.len, page=4096)

		# Copy in annotation data
		a = self._s.annotations[ann_no]
		a.type.val = typ
		a.fidx_start.val = fidx.start
		a.fidx_end.val = fidx.stop

		aa = a.condition_on('type')
		if typ == 'C':
			aoff = ann_C_struct.lenplan("")
			aa.index_comment_start.val = aoff
			aa.index_comment_end.val = aoff + len(parms['comment'])
			aa.comment.val = parms['comment']
		elif typ == 'D':
			aa.marker.val = parms['marker']
			aa.value.val = parms['value']
		elif typ == 'M':
			aa.marker.val = parms['marker']
		else:
			raise ValueError("Unrecognized annotation type '%s'" % typ)

		# Get file struct to update its properties
		f = self.wiff._chunks['INFO'].get_file_by_name(self.fw.fname)

		# Update annotations header
		self.aidx_end = self.aidx_start + ann_no
		# Update frame index range
		self.fidx_first = min(self.fidx_first, fidx.start)
		self.fidx_last = max(self.fidx_last, fidx.stop)


		# If this is the first frame, then need to set the start
		if ann_no == 0:
			self.aidx_start = ann_no

		# Add number of annotations to the end
		self.aidx_end = ann_no + 1

		# Update counter
		self.num_annotations = ann_no + 1
		self.wiff._chunks['INFO'].num_annotations += 1

		# Update file stats
		f.aidx_end.val = self.aidx_end
		f.fidx_start.val = self.fidx_first
		f.fidx_end.val = self.fidx_last


	def resize_add_page(self, val):
		"""
		Resize this chunk by adding @val pages of 4096 bytes.
		"""

		if val < 0:
			raise ValueError("Cannot shrink chunk by negative pages: %d" % val)

		self.resize_add(val * 4096)

	def resize_add(self, val):
		"""
		Resize this chunk by adding @val to the current size in bytes.
		If not a multiple of 4096 byte pages, it will be rounded up to the full page.
		"""

		if val < 0:
			raise ValueError("Cannot shrink chunk by negative bytes: %d" % val)

		# Take current size and add the supplied value
		self.resize(self.chunk.size + val)

	def resize(self, new_size):
		"""
		Resize this chunk to @val bytes.
		If not a multiple of 4096 byte pages, it will be rounded up to the full page.
		"""

		if new_size < self.chunk.size:
			raise ValueError("Cannot shrink chunk: %d" % val)

		# Get number of 4096 pages
		z = divmod(new_size, 4096)
		if z[1] != 0:
			# If a partial page, then incremeent to a full page
			pgs = z[0] + 1
		else:
			# Requested just the right number of frames to fill a full page (kudos)
			pgs = z[0]

		# Get new chunk size in bytes (4096 bytes per page)
		new_size = pgs * 4096

		# Actually resize the chunk
		WIFF_chunk.ResizeChunk(self.chunk, new_size)

