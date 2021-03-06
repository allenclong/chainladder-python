# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
import pandas as pd
import copy
import json


class _Workbook:
    """
    Excel Workbook level configurations.  This is not part of the end_user API
    """
    max_column_width = 30
    max_portrait_width = 120
    footer = '&CPage &P of &N\n&A'

    def __init__(self, workbook_path, exhibits, default_formats):
        self.formats = {}
        self.writer = pd.ExcelWriter(workbook_path)
        self.exhibits = exhibits
        self.workbook_path = workbook_path
        self.default_formats = {} if default_formats is None else default_formats

    def to_excel(self):
        """ Outputs object to Excel.

        Parameters:
        -----------
        workbook_path : str
            The target path and filename of the Excel document
        """
        if self.exhibits.__class__.__name__ != 'Tabs':
            self.exhibits = Tabs(('sheet1', self.exhibits))
        for sheet in self.exhibits:
            self._write(sheet[1], sheet[0])
        self.writer.save()
        self.writer.close()

    def _write(self, exhibit, sheet, start_row=0, start_col=0):
        klass = exhibit.__class__.__name__
        if getattr(exhibit, 'title', None) is not None:
            t = copy.deepcopy(exhibit.title)
            exhibit.title = None
            exhibit = Column(t, exhibit)
            self._write(exhibit, sheet, start_row, start_col)
        elif klass in ['Row', 'Column']:
            start_row = start_row + exhibit.margin[0]
            start_col = start_col + exhibit.margin[3]
            for item in exhibit.args:
                self._write(item, sheet, start_row, start_col)
                if klass == 'Column':
                    start_row = start_row + item.height
                if klass == 'Row':
                   start_col = start_col + item.width
        else:
            exhibit.start_row = start_row
            exhibit.start_col = start_col
            exhibit.sheet_name = sheet
            try:
                exhibit.worksheet = self.writer.sheets[exhibit.sheet_name]
            except:
                pd.DataFrame().to_excel(self.writer, sheet_name=exhibit.sheet_name)
                exhibit.worksheet = self.writer.sheets[exhibit.sheet_name]
            if klass == 'DataFrame':
                if exhibit.header:
                    self._write_header(exhibit)
                if exhibit.index:
                    self._write_index(exhibit)
                self._register_formats(exhibit)
                self._write_data(exhibit)
            if klass == '_Title':
                self._write_title(exhibit)
            #self._set_worksheet_properties(exhibit)

    def set_worksheet_properties(self, exhibit):
        ''' Format column widths, headers footers, etc.'''
        # exhibit.worksheet.hide_gridlines(2)
        exhibit.worksheet.set_footer(self.footer)
        widths = [min(self.max_column_width, item)
                  for item in exhibit.column_widths]
        widths[0] = 18 if widths[0] < 18 else widths[0]
        for num, item in enumerate(widths):
            col = exhibit.start_col + exhibit.index + num
            exhibit.worksheet.set_column(col, col, item)
        if sum(widths) > self.max_portrait_width:
            exhibit.worksheet.set_landscape()

    def _write_title(self, exhibit):
        start_row = exhibit.start_row + exhibit.margin[0]
        start_col = exhibit.start_col + exhibit.margin[3]
        end_row = start_row + exhibit.height
        end_col = start_col + exhibit.width - 1
        row_rng = range(start_row, end_row)
        title_format = []
        for item in exhibit.title_formats:
            v = self.default_formats.copy()
            v.update(item)
            title_format.append(self.writer.book.add_format(v))
        for r in row_rng:
            exhibit.worksheet.merge_range(
                r, start_col, r, end_col, exhibit.data.iloc[r - start_row][0],
                title_format[r - start_row])

    def _write_header(self, exhibit):
        ''' Adds column headers to data table '''
        if not exhibit.index:
            headers = exhibit.data.columns
        else:
            headers = [exhibit.index_label]+list(exhibit.data.columns)
        header_format = self.default_formats.copy()
        header_format.update(exhibit.header_formats)
        header_format = self.writer.book.add_format(header_format)
        for col_num, value in enumerate(headers):
            exhibit.worksheet.write(
                exhibit.start_row + exhibit.margin[0],
                col_num + exhibit.start_col + exhibit.margin[3],
                value, header_format)
            if exhibit.col_nums:
                exhibit.worksheet.write(
                    exhibit.start_row + 1, col_num, -col_num-1, header_format)

    def _write_index(self, exhibit):
        ''' Adds row index to data table '''
        index_format = self.default_formats.copy()
        index_format.update(exhibit.index_formats)
        index_format = self.writer.book.add_format(index_format)
        for row_num, value in enumerate(exhibit.data.index.astype(str)):
            exhibit.worksheet.write(
                row_num + exhibit.start_row + exhibit.header + \
                exhibit.col_nums + exhibit.margin[0],
                exhibit.start_col + exhibit.margin[3],
                value, index_format)

    def _register_formats(self, exhibit):
        """
        Registers all unique user-defined formats with the Workbook
        """
        for num, k in enumerate(exhibit.formats.keys()):
            # Add unique formats
            v = exhibit.formats[k]
            if type(v) is dict:
                col_formats = v
            elif type(v) is str:
                col_formats = {'num_format': v}
            else:
                raise ValueError(f'Cannot infer format {v}')
            col_formats = self.default_formats.copy()
            col_formats.update(v)
            if self.formats.get(json.dumps(col_formats), None) is None:
                self.formats[json.dumps(col_formats)] = \
                    self.writer.book.add_format(col_formats)

        for k in exhibit.formats.keys():
            # Assign formats to columns
            v = self.default_formats.copy()
            v.update(exhibit.formats[k])
            exhibit.formats[k] = self.formats[json.dumps(v)]

    def _write_data(self, exhibit):
        start_row = exhibit.start_row + exhibit.col_nums + exhibit.header + \
                    exhibit.margin[0]
        start_col = exhibit.start_col + exhibit.index + exhibit.margin[3]
        end_row = start_row + exhibit.data.shape[0]
        end_col = start_col + exhibit.data.shape[1]
        row_rng = range(start_row, end_row)
        col_rng = range(start_col, end_col)
        d = exhibit.data.fillna('').values
        for c in col_rng:
            c_idx = c - exhibit.index - exhibit.start_col - exhibit.margin[3]
            fmt = exhibit.formats[exhibit.data.columns[c_idx]]
            for r in row_rng:
                r_idx = r - exhibit.col_nums - exhibit.header - \
                        exhibit.start_row - exhibit.margin[0]
                exhibit.worksheet.write(r, c, d[r_idx, c_idx], fmt)
                if r == start_row:
                    exhibit.worksheet.set_column(
                        first_col=c, last_col=c,
                        width=exhibit.column_widths[c_idx])


class _Title:
    def __init__(self, data, width, title_formats, margin):
        if type(data) is str:
            data = [data]
        self.data = pd.DataFrame(data)
        self.title_formats = title_formats
        self.width = width
        self.height = len(self.data)
        self.header = False
        self.index = False
        self.col_nums = False
        self.margin = margin
        self.formats = {}

    def __len__(self):
        return len(self.data)

    @staticmethod
    def _default_title_format():
        return [{'font_size': 20, 'align': 'center'},
                {'font_size': 16, 'align': 'center'},
                {'font_size': 16, 'align': 'center'}] + \
               [{'font_size': 13, 'align': 'center'}]*10

    @staticmethod
    def _set_title_format(overlay):
        original = _Title._default_title_format()
        if overlay is not None:
            if type(overlay) is list:
                for num, item in enumerate(overlay):
                    original[num].update(item)
            else:
                for num, item in enumerate(original):
                    original[num].update(overlay)
        return original


class DataFrame:
    """
    Excel-ready DataFrame

    Parameters:
    -----------
    data : DataFrame or Triangle (2D)
        The data to be places in the exhibit
    formats : dict
        The formats to be applied to the data.  Options include
        'money', 'percent', 'decimal', 'date', 'int', and 'text'.  Each
        format can be overriden at the class level by overriding its:
        resepective format dict (e.g. DataFrame.money_format, ...)
    header : bool or list (len of data.columns)
        False uses no headers, True uses headers from data. Alternatively,
        a list of strings will override headers.
    header_formats : dict
        The formats to be applied to the header, if any
    col_nums : bool
        Set to True will insert column numbers into the exhibit.
    index : bool, default True
        Write row names (index).
    index_formats : dict
        The formats to be applied to the index, if any
    index_label : str or sequence, optional
        Column label for index column(s) if desired.
    title : list
        A list of strings up to length 4 (Title, subtitle1, subtitle2,
        subtitle3) to be placed above the data in the exhibit.
    title_formats : list of dicts
        Formats to be applied to the title.  title_formats length must equal
        the title length
    """

    min_numeric_col_width = 12
    # Padding since bold characters are slightly larger than regular
    # and need a bit more width
    col_padding_multiplier = 1.1

    def __init__(self, data, formats=None,
                 header=True, header_formats=None, col_nums=False,
                 index=True, index_label='', index_formats=None,
                 title=None, title_formats=None,
                 column_widths=None, margin=None):
        self.title_formats = _Title._set_title_format(title_formats)
        if type(title) is list:
            self.title_formats = self.title_formats[:len(title)]
        self.index_formats = {
            'num_format': '0;(0)', 'text_wrap': True,
            'bold': True, 'valign': 'bottom', 'align': 'center'}
        self.header_formats = {
            'num_format': '0;(0)', 'text_wrap': True, 'bottom': 1,
            'bold': True, 'valign': 'bottom', 'align': 'center'}
        if type(data) is not pd.DataFrame:
            data = data.to_frame()
        self.margin = _Container._set_margin(margin)
        self.data = data
        self.header = header
        self.index = index
        self.index_label = index_label
        self.col_nums = col_nums
        self.format_validation(formats)
        if column_widths is None:
            self.column_widths = self.get_column_widths()
        else:
            self.column_widths = column_widths
        self.height = data.shape[0] + self.col_nums + self.header + \
                      self.margin[0] + self.margin[2]
        self.width = data.shape[1] + self.index + self.margin[1] + \
                     self.margin[3]
        if title is None or title == []:
            title = None
        else:
            self.height = self.height + len(title)
            title = _Title(
                title, width=data.shape[1] + self.index,
                title_formats=self.title_formats,
                margin=(self.margin[0], 0, 0, self.margin[3]))
        self.title = title

        if header_formats is not None:
            self.header_formats.update(header_formats)
        if index_formats is not None:
            self.index_formats.update(index_formats)

    def to_excel(self, workbook_path, default_formats=None):
        """ Outputs object to Excel.

        Parameters:
        -----------
        workbook_path : str
            The target path and filename of the Excel document
        """
        _Workbook(workbook_path=workbook_path, exhibits=self,
                  default_formats=default_formats).to_excel()

    def get_column_widths(self):
        header_w = [max([len(token) for token in str(item).split(' ')])
                    * self.col_padding_multiplier
                    for item in self.data.columns]
        numeric_cols = self.data.select_dtypes('number').columns
        row_w = [(self.min_numeric_col_width if item in numeric_cols
                  else max(self.data[item].astype(str).str.len())
                  * self.col_padding_multiplier)
                 for item in self.data.columns]
        return [max(item) for item in zip(header_w, row_w)]

    def format_validation(self, formats):
        ''' Creates an Excel format compatible dictionary '''
        base_formats = {
            'float64': {'num_format': '#,0.00'},
            'float32': {'num_format': '#,0.00'},
            'int64': {'num_format': '#,0'},
            'int32': {'num_format': '#,0'},
            '<M8[ns]': {'num_format': 'yyyy-mm-dd hh:mm'},
            'object': {'align': 'left'},
        }
        self.formats = {
            k: base_formats[v]
            for k, v in dict(self.data.dtypes.astype(str)).items()
        }
        if type(formats) is list:
            self.formats.update(dict(zip(self.data.columns, formats)))
        elif type(formats) is str:
            self.formats.update(dict(zip(
                self.data.columns,
                [{'num_format': formats}] * len(self.data.columns))))
        elif type(formats) is dict:
            if list(formats.keys())[0] not in self.data.columns:
                self.formats.update(dict(zip(
                    self.data.columns,
                    [formats] * len(self.data.columns))))
            else:
                self.formats.update(formats)
        else:
            pass

class _Container():
    """ Base class for Row and Column
    """
    def __init__(self, *args, **kwargs):
        if len(args) != len(set(args)):
            self.args = tuple([copy.deepcopy(item) for item in args])
        else:
            self.args = args
        self.margin = _Container._set_margin(kwargs.get('margin', None))
        self._title_len = 0
        if kwargs.get('title_formats', None) is not None:
            self.title_formats = _Title._set_title_format(kwargs['title_formats'])
            if type(kwargs['title']) is list:
                self.title_formats = self.title_formats[:len(kwargs['title'])]
        if kwargs.get('title', None) is not None:
            if kwargs.get('title_formats', None) is None:
                self.title_formats = _Title._default_title_format()
            self.title = _Title(
                kwargs['title'], width=self.width,
                title_formats=self.title_formats, margin=(0, 0, 0, 0))
            if getattr(self, 'title', None) is not None:
                self._title_len = len(getattr(self, 'title'))


        arg_title = [0]
        for item in args:
            if getattr(item, 'title', None) is not None:
                arg_title.append(len(getattr(item, 'title')))
        self._arg_title_len = arg_title

    def __getitem__(self, key):
        return self.args[key]

    def __len__(self):
        return len(self.args)

    def to_excel(self, workbook_path, default_formats=None):
        """ Outputs object to Excel.

        Parameters:
        -----------
        workbook_path : str
            The target path and filename of the Excel document
        """
        _Workbook(workbook_path=workbook_path, exhibits=self,
                  default_formats=default_formats).to_excel()

    @staticmethod
    def _set_margin(margin):
        if type(margin) is int:
            return (margin, margin, margin, margin)
        elif margin is None:
            return (0, 0, 0, 0)
        elif type(margin) is tuple and len(margin) == 2:
            return (margin[0], margin[1], margin[0], margin[1])
        else:
            return margin


class Row(_Container):
    """
    Lay out child components in a single horizontal row.
    Children can be specified as positional arguments, as a single argument
    that is a sequence.

    Parameters
    ----------
    args:
        Children can be of the chainlader DataFrame, Row, and Column classes.
    title: optional (str or list)
        The title to be displayed across the top of the container.  Must be
        specified using the keyword `title=`
    margin:
        Cell margins to put around the container.  Can be expressed as an int
        or a 2-tuple or a 4-tuple.  The tuple style follows CSS margin guidelines
        which generally start from the top and work around clockwise.

    Attributes
    ----------
    height : int
        Height of the container and is a function of the elements it contains
    width : int
        Width of the container and is a function of the elements it contains

    """
    @property
    def height(self):
        margin = self.margin[0] + self.margin[2]
        return max([item.height for item in self.args]) + \
               max(self._arg_title_len) + margin + self._title_len

    @property
    def width(self):
        margin = self.margin[1] + self.margin[3]
        return sum([item.width for item in self.args]) + margin


class Column(_Container):
    """
    Lay out child components in a single vertical column.
    Children can be specified as positional arguments, as a single argument
    that is a sequence.

    Parameters
    ----------
    args:
        Children can be of the chainlader DataFrame, Row, and Column classes.
    title: optional (str or list)
        The title to be displayed across the top of the container.  Must be
        specified using the keyword `title=`
    margin:
        Cell margins to put around the container.  Can be expressed as an int
        or a 2-tuple or a 4-tuple.  The tuple style follows CSS margin guidelines
        which generally start from the top and work around clockwise.

    Attributes
    ----------
    height : int
        Height of the container and is a function of the elements it contains
    width : int
        Width of the container and is a function of the elements it contains

    """
    @property
    def height(self):
        margin = self.margin[0] + self.margin[2]
        return sum([item.height for item in self.args]) + \
               sum(self._arg_title_len) + margin + self._title_len

    @property
    def width(self):
        margin = self.margin[1] + self.margin[3]
        return max([item.width for item in self.args]) + margin


class Tabs:
    """
    Layout exhibits across worksheets.

    Parameters
    ----------
    args:
        Children must be a tuple with a sheet name and any of chainlader
        DataFrame, Row, and Column classes.  For example,
        ('sheet1', cl.DataFrame(data))
    """

    def __init__(self, *args, **kwargs):
        if len(args) != set([item[1] for item in args]):
            self.args = tuple([(item[0], copy.deepcopy(item[1]))
                               for item in args])
        else:
            self.args = args

    def __getitem__(self, key):
        return self.args[key]

    def __len__(self):
        return len(self.args)

    def to_excel(self, workbook_path, default_formats=None):
        """ Outputs object to Excel.

        Parameters:
        -----------
        workbook_path : str
            The target path and filename of the Excel document

        """
        _Workbook(workbook_path=workbook_path, exhibits=self,
                  default_formats=default_formats).to_excel()
