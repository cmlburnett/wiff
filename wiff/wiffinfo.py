
import datetime

from .structs import info_struct, channel_struct, file_struct
from .util import DATE_FMT

class WIFFINFO:
	"""
	Helper class that interfaces the data portion of a WIFFINFO chunk.
	This chunk includes all of the meta data about the recording (start time, end time, sampling frequency, etc).
	"""

	def __init__(self, wiff, fw, chunk):
		"""
		Manage a WIFFINFO chunk using the _filewrap object @fw.
		Supply the absolute offset @offset the chunk is located at in the file.
		aLL OPErations are using an mmap and there is no caching.
		"""
		self.wiff = wiff
		self.fw = fw
		self.chunk = chunk

		self._s = info_struct(fw, self.chunk.data_offset)

	@property
	def offset(self): return self._s.offset

	def initchunk(self):
		"""
		Initiailizes a new chunk for this chunk type.
		"""
		self.chunk.magic = 'WIFFINFO'
		self.chunk.size = 4096
		# Version 1
		self.chunk.attributes = (1,0,0,0, 0,0,0,0)

	def initheader(self, start, end, desc, fs, num_frames, num_annotations, num_metas, channels, files):
		"""
		Initializes a new header
		This requires explicit initialization of all the byte indices.
		"""

		self.index_start = info_struct.lenplan("","","", [], [])
		self.index_end = self.index_start + len(start.strftime(DATE_FMT))
		self.index_description = self.index_end + len(end.strftime(DATE_FMT))
		self.index_channels = self.index_description + len(desc)

		self.fs = fs
		self.num_frames = num_frames
		self.num_annotations = num_annotations
		self.num_channels = len(channels)
		self.num_files = len(files)
		self.num_metas = num_metas

		self.start = start.strftime(DATE_FMT)
		self.end = end.strftime(DATE_FMT)
		self.description = desc

		# This also sets the index_files_start because it depends on length of the channels
		self._initchannels(channels)

		# This also sets the indes_files_end
		self._initfiles(files)


	def _initchannels(self, chans):
		self.num_channels = len(chans)

		# Size of the jumptable
		strt = self._s.channels_jumptable.sizeof
		for i in range(len(chans)):
			c = chans[i]

			sz = channel_struct.lenplan(c['name'], c['unit'], c['comment'])

			self._s.channels_jumptable[i] = (strt, strt+sz)
			strt += sz

			off = channel_struct.lenplan("","","")

			ln_name = len(c['name'])
			ln_unit = len(c['unit'])
			ln_comment = len(c['comment'])

			self._s.channels[i].index.val = i
			self._s.channels[i].index_name.val = off
			self._s.channels[i].index_unit.val = off + ln_name
			self._s.channels[i].index_comment_start.val = off + ln_name + ln_unit
			self._s.channels[i].index_comment_end.val = off + ln_name + ln_unit + ln_comment

			self._s.channels[i].bit.val = c['bit']

			self._s.channels[i].name.val = c['name']
			self._s.channels[i].unit.val = c['unit']
			self._s.channels[i].comment.val = c['comment']

		# Get the last byte used by the last entry as the start for the files
		self.index_file_start = self._s.channels_jumptable[-1][1] + self._s.channels_jumptable.offset


	def _initfiles(self, files):
		self.index_file_end = self.index_file_start

		self.num_files = 0

		for i in range(len(files)):
			f = files[i]
			self.add_file(f['name'], f['fidx_start'], f['fidx_end'], f['aidx_start'], f['aidx_end'])

	@property
	def magic(self): return self.chunk.magic

	@property
	def index_start(self): return self._s.index_start.val
	@index_start.setter
	def index_start(self, val): self._s.index_start.val = val

	@property
	def index_end(self): return self._s.index_end.val
	@index_end.setter
	def index_end(self, val): self._s.index_end.val = val

	@property
	def index_description(self): return self._s.index_description.val
	@index_description.setter
	def index_description(self, val): self._s.index_description.val = val

	@property
	def index_channels(self): return self._s.index_channels.val
	@index_channels.setter
	def index_channels(self, val): self._s.index_channels.val = val

	@property
	def index_file_start(self): return self._s.index_file_start.val
	@index_file_start.setter
	def index_file_start(self, val): self._s.index_file_start.val = val

	@property
	def index_file_end(self): return self._s.index_file_end.val
	@index_file_end.setter
	def index_file_end(self, val): self._s.index_file_end.val = val

	@property
	def fs(self): return self._s.fs.val
	@fs.setter
	def fs(self, val): self._s.fs.val = val

	@property
	def num_channels(self): return self._s.num_channels.val
	@num_channels.setter
	def num_channels(self, val): self._s.num_channels.val = val

	@property
	def num_files(self): return self._s.num_files.val
	@num_files.setter
	def num_files(self, val): self._s.num_files.val = val

	@property
	def num_frames(self): return self._s.num_frames.val
	@num_frames.setter
	def num_frames(self, val): self._s.num_frames.val = val

	@property
	def num_annotations(self): return self._s.num_annotations.val
	@num_annotations.setter
	def num_annotations(self, val): self._s.num_annotations.val = val

	@property
	def num_metas(self): return self._s.num_metas.val
	@num_metas.setter
	def num_metas(self, val): self._s.num_metas.val = val


	@property
	def start(self):
		return self._s.start.val
	@start.setter
	def start(self, val):
		if isinstance(val, datetime.datetime):
			val = val.strftime(DATE_FMT)
		else:
			pass

		exist = self.index_end - self.index_start
		if len(val) == exist:
			self._s.start.val = val
		else:
			raise NotImplementedError

	@property
	def end(self):
		return self._s.end.val
	@end.setter
	def end(self, val):
		if isinstance(val, datetime.datetime):
			val = val.strftime(DATE_FMT)
		else:
			pass

		if len(val) == len(self._s.end.val):
			self._s.end.val = val
		else:
			raise NotImplementedError

	@property
	def description(self):
		return self._s.description.val
	@description.setter
	def description(self, val):
		if len(val) == len(self._s.description.val):
			self._s.description.val = val
		else:
			raise NotImplementedError

	@property
	def channels(self): return self._s.channels

	@property
	def files(self): return self._s.files

	def get_file_by_name(self, fname):
		for i in range(len(self._s.files)):
			f = self._s.files[i]
			if f.name.val == fname:
				return f

		raise ValueError("File not found with name '%s'" % fname)


	def add_file(self, fname, fidx_start, fidx_end, aidx_start, aidx_end):
		"""
		Adds a new file to the list
		"""

		# Get length of new file entry
		ln = file_struct.lenplan(fname)

		# Get current size of chunk and end index of last file entry
		cur_size = self.chunk.size
		cur_end = self.index_file_end

		# If current end plus new file struct plus 4 for jumptable entry is more than current size, bump it up a page
		if cur_end + ln + 4 > cur_size:
			WIFF_chunk.ResizeChunk(self.chunk, cur_size + 4096)

		# Get current number of files, which is also the index of the next jumptable entry
		fnum = self._s.num_files.val


		# Add new entry to the jumptable
		idx = self._s.files.add(ln, start=12, page=12)
		entry = self._s.files_jumptable[idx]

		# Offset is relative to jumptable, so add in offset of the jumptable
		self.index_file_end = entry[1] + self._s.files_jumptable.offset

		# Offset into file_struct where name starts
		off = file_struct.lenplan("")

		# Set file information
		self._s.files[fnum].index.val = fnum
		self._s.files[fnum].index_name_start.val = off
		self._s.files[fnum].index_name_end.val = off + len(fname)
		self._s.files[fnum].fidx_start.val = fidx_start
		self._s.files[fnum].fidx_end.val = fidx_end
		self._s.files[fnum].aidx_start.val = aidx_start
		self._s.files[fnum].aidx_end.val = aidx_end
		self._s.files[fnum].name.val = fname

