
import datetime
import sys

def slice_to_gen(s):
	"""
	Slice objects can not be iterated, so run a generator over the parameters of the slice.
	"""

	start = s.start or 1
	step = s.step or 1
	stop = s.stop or sys.maxsize

	for i in range(start, stop, step):
		yield i

# ------------------------------------------------------------------------
# ------------------------------------------------------------------------
# Generic base classes

class _WIFF_obj:
	"""
	Every object accepts the main WIFF object and copies in the DB object.
	"""

	def __init__(self, w):
		""" Initialize with the given WIFF object. """
		self._w = w
		self._db = w.db

class _WIFF_obj_list(_WIFF_obj):
	"""
	Intended for list item style access to a type using the rowid as the key.

	keys(), values(), items() return ata like the same functions on dict()
	len() call on this object does a row count.
	foo[rowid] gets a specific item with the rowid
	"""

	def _query(self):
		return self._sub_d.select('rowid')
	def _query_len(self):
		return self._sub_d.num_rows()

	def keys(self):
		res = self._query()
		rows = [_['rowid'] for _ in res]
		return rows

	def values(self):
		_t = self._sub_type
		return [_t(self._w, _) for _ in self.keys()]

	def items(self):
		return [(_, _t(self._w, _)) for _ in self.keys()]

	def __iter__(self):
		for k in self.keys():
			yield k

	def __len__(self):
		return self._query_len()

	def __getitem__(self, k):
		return self._sub_type(self._w, k)

class _WIFF_obj_item(_WIFF_obj):
	"""
	Intended for individual object access

	refresh() reloads the data from the database as no attempt is made to keep this object consistent.
	id property is available on all objects as the rowid value.
	"""

	def __init__(self, w, _id, meta_name):
		"""
		Provide the rowid as @_id and the @meta_name is the name (eg, 'recording') which should be the table name in the DB.
		"""

		super().__init__(w)

		# Pull out the sub table object from the database for this object
		self._sub_d = getattr(w.db, meta_name)

		self._id = _id

		# Load in data now (rather than lazy loading)
		self.refresh()

	def refresh(self):
		"""Reload the data from the database"""
		self._data = self._sub_d.select_one('*', '`rowid`=?', [self._id])

	@property
	def id(self): return self._id

# ------------------------------------------------------------------------
# ------------------------------------------------------------------------
# Specific object types

class WIFF_recordings(_WIFF_obj_list):
	"""
	Handle WIFF.recording access to the recordings in the file.
	"""
	def __init__(self, w):
		self._sub_d = w.db.recording
		self._sub_type = WIFF_recording

		super().__init__(w)

class WIFF_recording_segments(_WIFF_obj_list):
	"""
	Handle WIFF.recording[x].segment as filtered segments by the recording ID.
	"""
	def __init__(self, w, id_recording):
		self._id_recording = id_recording

		self._sub_d = w.db.segment
		self._sub_type = WIFF_segment

		super().__init__(w)

	# Change these queries to filter by id_recording
	def _query(self):
		return self._sub_d.select('rowid', '`id_recording`=?', [self._id_recording])
	def _query_len(self):
		return self._sub_d.num_rows('`id_recording`=%d' % self._id_recording)

class WIFF_recording_metas(_WIFF_obj_list):
	"""
	Handle WIFF.recording[x].meta as filtered metas by the recording ID.
	"""
	def __init__(self, w, id_recording):
		self._id_recording = id_recording

		self._sub_d = w.db.meta
		self._sub_type = WIFF_meta

		super().__init__(w)

	# Change these queries to filter by id_recording
	def _query(self):
		return self._sub_d.select('rowid', '`id_recording`=?', [self._id_recording])
	def _query_len(self):
		return self._sub_d.num_rows('`id_recording`=%d' % self._id_recording)

class WIFF_recording_channels(_WIFF_obj_list):
	"""
	Handle WIFF.recording[x].channel as filtered channels by the recording ID.
	"""
	def __init__(self, w, id_recording):
		self._id_recording = id_recording

		self._sub_d = w.db.channel
		self._sub_type = WIFF_channel

		super().__init__(w)

	# Change these queries to filter by id_recording
	def _query(self):
		return self._sub_d.select('rowid', '`id_recording`=?', [self._id_recording])
	def _query_len(self):
		return self._sub_d.num_rows('`id_recording`=%d' % self._id_recording)

class WIFF_recording_annotations(_WIFF_obj_list):
	"""
	Handle WIFF.recording[x].annotation as filtered annotations by the recording ID.
	"""
	def __init__(self, w, id_recording):
		self._id_recording = id_recording

		self._sub_d = w.db.annotation
		self._sub_type = WIFF_annotation

		super().__init__(w)

	# Change these queries to filter by id_recording
	def _query(self):
		return self._sub_d.select('rowid', '`id_recording`=?', [self._id_recording])
	def _query_len(self):
		return self._sub_d.num_rows('`id_recording`=%d' % self._id_recording)

class WIFF_recording_frames(_WIFF_obj):
	"""
	Handle WIFF.recording[x].frame as filtered frames by the recording ID.
	"""
	def __init__(self, w, id_recording):
		self._id_recording = id_recording

		super().__init__(w)

	def __getitem__(self, k):
		if type(k) is int:
			if k <= 0:
				raise ValueError("Frame indices start with 1, cannot get zero or negative indices (%d)" % k)

			row = self._db.segment.select_one(['rowid','id_blob'], '`fidx_start`<=? and `fidx_end`>=? and `id_recording`=?', [k,k, self._id_recording])
			if row is None:
				raise ValueError("No segment for this recording (%d) contains the frame %d" % (self._id_recording, k))

			seg = WIFF_segment(self._w, row['rowid'])
			b = WIFF_blob(self._w, row['id_blob'])

			ret = []
			# Calculate sum total of channels
			stride = []
			for cs in seg.channelset:
				stride.append(cs.channel.storage)

			# How many frames into the blob to read
			offset = (k - seg.fidx_start) * sum(stride)

			# TODO: handle decompression

			for s in stride:
				ret.append( b.data[offset:offset+s] )
				offset += s

			return tuple(ret)


		elif type(k) is slice:
			if k.start is None:
				k = slice(1, k.stop, k.step)
			if k.start <= 0:
				raise ValueError("Frame indices start with 1, cannot get zero or negative indices (%d)" % k.start)

			# Inefficient way to handle slices but it works
			if k.stop is None:
				end = self._w.fidx_end(self._id_recording)

				k = slice(k.start, end+1, k.step)
			return [self[_] for _ in slice_to_gen(k)]

		else:
			raise TypeError("Unable to handle this type: %s" % k)


class WIFF_frame_table(_WIFF_obj):
	"""
	Handle WIFF.recording[x].frame_table as a way to access segments, etc.
	"""
	def __init__(self, w, id_recording):
		self._id_recording = id_recording

		super().__init__(w)

		self.refresh()

	def refresh(self):
		res = self._db.segment.select('rowid', '`id_recording`=?', [self._id_recording])
		rows = [WIFF_segment(self._w, _['rowid']) for _ in res]

		# Reset min and max
		self._fidx_start = None
		self._fidx_end = None

		ends = []
		self._table = {}
		for row in rows:
			# fidx_end is inclusive and r.stop is exclusive so have to add 1
			r = range(row.fidx_start, row.fidx_end+1)
			self._table[r] = row

			ends.append(row.fidx_start)
			ends.append(row.fidx_end)

		# Find the ends
		self._fidx_start = min(ends)
		self._fidx_end = max(ends)

	@property
	def fidx_start(self): return self._fidx_start

	@property
	def fidx_end(self): return self._fidx_end

	def get_segment(self, fidx):
		"""
		Gets the segment for the given frame index @fidx.
		"""

		if fidx <= 0:
			raise ValueError("Frame indices start with 1, cannot get zero or negative indices (%d)" % fidx)

		for r in self._table:
			if fidx in r:
				return self._table[r]

		raise ValueError("Frame index %d not found in this recording" % fidx)

	def __getitem__(self, k):
		r = WIFF_recording(self._w, self._id_recording)
		return r.frame[k]

class WIFF_recording(_WIFF_obj_item):
	"""
	Handle WIFF.recording[x] as filtered by the recording ID and access to recording specific lists like channels, metas, and frames.
	"""
	def __init__(self, w, _id):
		super().__init__(w, _id, 'recording')

	@property
	def start(self): return self._data['start']

	@property
	def end(self): return self._data['end']

	@property
	def description(self): return self._data['description']

	@property
	def sampling(self): return self._data['sampling']

	@property
	def segment(self): return WIFF_recording_segments(self._w, self._id)

	@property
	def meta(self): return WIFF_recording_metas(self._w, self._id)

	@property
	def channel(self): return WIFF_recording_channels(self._w, self._id)

	@property
	def annotation(self): return WIFF_recording_annotations(self._w, self._id)

	@property
	def frame(self): return WIFF_recording_frames(self._w, self._id)

	@property
	def frame_table(self):
		return WIFF_frame_table(self._w, self._id)

# ----------------------------------------

class WIFF_segments(_WIFF_obj_list):
	"""
	Handle WIFF.segment access to all segments in the file.
	"""
	def __init__(self, w):
		self._sub_d = w.db.segment
		self._sub_type = WIFF_segment

		super().__init__(w)

class WIFF_segment(_WIFF_obj_item):
	"""
	Handle WIFF.segment[x] access to a specific segment.
	"""
	def __init__(self, w, _id):
		super().__init__(w, _id, 'segment')

	@property
	def id_recording(self): return self._data['id_recording']

	@property
	def recording(self): return self._w.recording[ self._data['id_recording'] ]

	@property
	def idx(self): return self._data['idx']

	@property
	def fidx_start(self): return self._data['fidx_start']

	@property
	def fidx_end(self): return self._data['fidx_end']

	@property
	def channelset_id(self): return self._data['channelset_id']

	@property
	def stride(self): return self._data['stride']

	@property
	def channelset(self):
		res = self._db.channelset.select('rowid', '`set`=?', [self._data['channelset_id']])
		return [WIFF_channelset(self._w, _['rowid']) for _ in res]

	@property
	def id_blob(self): return self._data['id_blob']

	@property
	def blob(self): return self._w.blob[ self._data['id_blob'] ]

# ----------------------------------------

class WIFF_blobs(_WIFF_obj_list):
	"""
	Handle WIFF.blob access to all blobs in the file.
	"""
	def __init__(self, w):
		self._sub_d = w.db.blob
		self._sub_type = WIFF_blob

		super().__init__(w)

class WIFF_blob(_WIFF_obj_item):
	"""
	Handle WIFF.blob[x] access to a specific blob.
	"""
	def __init__(self, w, _id):
		super().__init__(w, _id, 'blob')

	@property
	def compression(self): return self._data['compression']

	@property
	def data(self): return self._data['data']

# ----------------------------------------

class WIFF_metas(_WIFF_obj_list):
	"""
	Handle WIFF.meta access to all metas in the file.
	"""
	def __init__(self, w):
		self._sub_d = w.db.meta
		self._sub_type = WIFF_meta

		super().__init__(w)

	def find_as_dict(self, *args, **kwargs):
		"""
		Same as find(), but changes list to a dictionary keyed on the meta.key value.
		"""
		rows = self.find(*args, **kwargs)
		return {_.key:_ for _ in rows}

	def find(self, id_recording, key):
		"""
		Find a meta value with key @key that accepts a limited wildcard.
		Keys are intended to be a dotted structural notation, and if the last part is an asterisk then it is substituted
		Thus, find(None, 'WIFF.*' will get all keys starting with 'WIFF.' such as 'WIFF.version' and 'WIFF.ctime'.

		Returned as a list of WIFF_meta objects.
		"""
		has_wild = False

		parts = key.split('.')
		if len(parts) > 1:
			if parts[-1] == '*':
				has_wild = True

				# Escape percent signs
				parts[0:-1] = [_.replace('%', '%%') for _ in parts[0:-1]]
				# Exchange * for % to wild card SQL search
				parts[-1] = '%'
				key = '.'.join(parts)

		if has_wild:
			if id_recording is None:
				res = self._sub_d.select('rowid', '`id_recording` is null and `key` like ?', [key])
			else:
				res = self._sub_d.select('rowid', '`id_recording`=? and `key` like ?', [id_recording, key])

		# No wilds
		else:
			if id_recording is None:
				res = self._sub_d.select('rowid', '`id_recording` is null and `key`=?', [key])
			else:
				res = self._sub_d.select('rowid', '`id_recording`=? and `key`=?', [id_recording, key])

		return [self._sub_type(self._w, _['rowid']) for _ in res]

class WIFF_meta(_WIFF_obj_item):
	"""
	Handle WIFF.meta[x] access to a specific segment.
	"""
	def __init__(self, w, _id):
		super().__init__(w, _id, 'meta')

	@property
	def key(self): return self._data['key']

	@property
	def type(self): return self._data['type']

	@property
	def raw_value(self):
		return self._data['value']

	@property
	def value(self):
		t = self.type
		v = self.raw_value

		if t == 'int':
			return int(v)
		elif t == 'str':
			return v
		elif t == 'datetime':
			return datetime.datetime.strptime(v, "%Y-%m-%d %H:%M:%S.%f")
		elif t == 'bool':
			return bool(int(v))
		elif t == 'blob':
			# Interpret value as an id_blob
			return WIFF_blob(self._w, int(v))
		else:
			raise TypeError("Unrecognized meta value type '%s' for value '%s'" % (t,v))

# ----------------------------------------

class WIFF_channels(_WIFF_obj_list):
	"""
	Handle WIFF.channel access to all channels in the file.
	"""
	def __init__(self, w):
		self._sub_d = w.db.channel
		self._sub_type = WIFF_channel

		super().__init__(w)

class WIFF_channel(_WIFF_obj_item):
	"""
	Handle WIFF.channel[x] access to a specific channel.
	"""
	def __init__(self, w, _id):
		super().__init__(w, _id, 'channel')

	@property
	def id_recording(self): return self._data['id_recording']

	@property
	def idx(self): return self._data['idx']

	@property
	def bits(self): return self._data['bits']

	@property
	def storage(self): return self._data['storage']

	@property
	def name(self): return self._data['name']

	@property
	def unit(self): return self._data['unit']

	@property
	def comment(self): return self._data['comment']

# ----------------------------------------

class WIFF_channelsets(_WIFF_obj_list):
	"""
	Handle WIFF.channelset access to all channelsets in the file.
	"""
	def __init__(self, w):
		self._sub_d = w.db.channelset
		self._sub_type = WIFF_channelset

		super().__init__(w)

class WIFF_channelset(_WIFF_obj_item):
	"""
	Handle WIFF.channelset[x] access to a specific segment.
	"""
	def __init__(self, w, _id):
		super().__init__(w, _id, 'channelset')

	@property
	def set(self): return self._data['set']

	@property
	def id_channel(self): return self._data['id_channel']

	@property
	def channel(self): return WIFF_channel(self._w, self._data['id_channel'])

# ----------------------------------------

class WIFF_annotations(_WIFF_obj_list):
	"""
	Handle WIFF.annotation access to all annotations in the file.
	"""
	def __init__(self, w):
		self._sub_d = w.db.annotation
		self._sub_type = WIFF_annotation

		super().__init__(w)

class WIFF_annotation(_WIFF_obj_item):
	"""
	Handle WIFF.annotation[x] access to a specific annotation.
	"""
	def __init__(self, w, _id):
		super().__init__(w, _id, 'annotation')

	@property
	def id_recording(self): return self._data['id_recording']

	@property
	def fidx_start(self): return self._data['fidx_start']

	@property
	def fidx_end(self): return self._data['fidx_end']

	@property
	def type(self): return self._data['type']

	@property
	def comment(self): return self._data['comment']

	@property
	def marker(self): return self._data['marker']

	@property
	def data(self): return self._data['data']

