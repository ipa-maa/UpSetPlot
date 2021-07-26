from __future__ import print_function, division, absolute_import
from numbers import Number
import functools
import distutils
import warnings
import re
import itertools

import pandas as pd
import numpy as np


_concat = pd.concat
if distutils.version.LooseVersion(pd.__version__) >= '0.23.0':
    # silence the warning
    _concat = functools.partial(_concat, sort=False)


def generate_samples(seed=0, n_samples=10000, n_categories=3):
    """Generate artificial samples assigned to set intersections

    Parameters
    ----------
    seed : int
        A seed for randomisation
    n_samples : int
        Number of samples to generate
    n_categories : int
        Number of categories (named "cat0", "cat1", ...) to generate

    Returns
    -------
    DataFrame
        Field 'value' is a weight or score for each element.
        Field 'index' is a unique id for each element.
        Index includes a boolean indicator mask for each category.

        Note: Further fields may be added in future versions.

    See Also
    --------
    generate_counts : Generates the counts for each subset of categories
        corresponding to these samples.
    """
    rng = np.random.RandomState(seed)
    df = pd.DataFrame({'value': np.zeros(n_samples)})
    for i in range(n_categories):
        r = rng.rand(n_samples)
        df['cat%d' % i] = r > rng.rand()
        df['value'] += r

    df.reset_index(inplace=True)
    df.set_index(['cat%d' % i for i in range(n_categories)], inplace=True)
    return df


def generate_counts(seed=0, n_samples=10000, n_categories=3):
    """Generate artificial counts corresponding to set intersections

    Parameters
    ----------
    seed : int
        A seed for randomisation
    n_samples : int
        Number of samples to generate statistics over
    n_categories : int
        Number of categories (named "cat0", "cat1", ...) to generate

    Returns
    -------
    Series
        Counts indexed by boolean indicator mask for each category.

    See Also
    --------
    generate_samples : Generates a DataFrame of samples that these counts are
        derived from.
    """
    df = generate_samples(seed=seed, n_samples=n_samples,
                          n_categories=n_categories)
    return df.value.groupby(level=list(range(n_categories))).count()


def generate_data(seed=0, n_samples=10000, n_sets=3, aggregated=False):
    warnings.warn('generate_data was replaced by generate_counts in version '
                  '0.3 and will be removed in version 0.4.',
                  DeprecationWarning)
    if aggregated:
        return generate_counts(seed=seed, n_samples=n_samples,
                               n_categories=n_sets)
    else:
        return generate_samples(seed=seed, n_samples=n_samples,
                                n_categories=n_sets)['value']


def _memberships_to_indicators(memberships):
    df = pd.DataFrame([{name: True for name in names}
                       for names in memberships])
    for set_name in df.columns:
        if not hasattr(set_name, 'lower'):
            raise ValueError('Category names should be strings')
    if df.shape[1] == 0:
        raise ValueError('Require at least one category. None were found.')
    df.sort_index(axis=1, inplace=True)
    df.fillna(False, inplace=True)
    df = df.astype(bool)
    return df


def _contents_to_indicators(contents):
    cat_series = [pd.Series(True, index=list(elements), name=name)
                  for name, elements in contents.items()]
    if not all(s.index.is_unique for s in cat_series):
        raise ValueError('Got duplicate ids in a category')

    df = _concat(cat_series, axis=1)
    df.fillna(False, inplace=True)
    return df


def from_memberships(memberships, data=None):
    """Load data where each sample has a collection of category names

    The output should be suitable for passing to `UpSet` or `plot`.

    Parameters
    ----------
    memberships : sequence of collections of strings
        Each element corresponds to a data point, indicating the sets it is a
        member of.  Each category is named by a string.
    data : Series-like or DataFrame-like, optional
        If given, the index of category memberships is attached to this data.
        It must have the same length as `memberships`.
        If not given, the series will contain the value 1.

    Returns
    -------
    DataFrame or Series
        `data` is returned with its index indicating category membership.
        It will be a Series if `data` is a Series or 1d numeric array.
        The index will have levels ordered by category names.

    Examples
    --------
    >>> from upsetplot import from_memberships
    >>> from_memberships([
    ...     ['cat1', 'cat3'],
    ...     ['cat2', 'cat3'],
    ...     ['cat1'],
    ...     []
    ... ])  # doctest: +ELLIPSIS, +NORMALIZE_WHITESPACE
    cat1   cat2   cat3
    True   False  True     1
    False  True   True     1
    True   False  False    1
    False  False  False    1
    Name: ones, dtype: ...
    >>> # now with data:
    >>> import numpy as np
    >>> from_memberships([
    ...     ['cat1', 'cat3'],
    ...     ['cat2', 'cat3'],
    ...     ['cat1'],
    ...     []
    ... ], data=np.arange(12).reshape(4, 3))  # doctest: +NORMALIZE_WHITESPACE
                       0   1   2
    cat1  cat2  cat3
    True  False True   0   1   2
    False True  True   3   4   5
    True  False False  6   7   8
    False False False  9  10  11
    """
    df = _memberships_to_indicators(memberships)
    df.set_index(list(df.columns), inplace=True)
    if data is None:
        return df.assign(ones=1)['ones']

    if hasattr(data, 'loc'):
        data = data.copy(deep=False)
    elif len(data) and isinstance(data[0], Number):
        data = pd.Series(data)
    else:
        data = pd.DataFrame(data)
    if len(data) != len(df):
        raise ValueError('memberships and data must have the same length. '
                         'Got len(memberships) == %d, len(data) == %d'
                         % (len(memberships), len(data)))
    data.index = df.index
    return data


def from_contents(contents, data=None, id_column='id'):
    """Build data from category listings

    Parameters
    ----------
    contents : Mapping (or iterable over pairs) of strings to sets
        Keys are category names, values are sets of identifiers (int or
        string).
    data : DataFrame, optional
        If provided, this should be indexed by the identifiers used in
        `contents`.
    id_column : str, default='id'
        The column name to use for the identifiers in the output.

    Returns
    -------
    DataFrame
        `data` is returned with its index indicating category membership,
        including a column named according to id_column.
        If data is not given, the order of rows is not assured.

    Notes
    -----
    The order of categories in the output DataFrame is determined from
    `contents`, which may have non-deterministic iteration order.

    Examples
    --------
    >>> from upsetplot import from_contents
    >>> contents = {'cat1': ['a', 'b', 'c'],
    ...             'cat2': ['b', 'd'],
    ...             'cat3': ['e']}
    >>> from_contents(contents)  # doctest: +NORMALIZE_WHITESPACE
                      id
    cat1  cat2  cat3
    True  False False  a
          True  False  b
          False False  c
    False True  False  d
          False True   e
    >>> import pandas as pd
    >>> contents = {'cat1': [0, 1, 2],
    ...             'cat2': [1, 3],
    ...             'cat3': [4]}
    >>> data = pd.DataFrame({'favourite': ['green', 'red', 'red',
    ...                                    'yellow', 'blue']})
    >>> from_contents(contents, data=data)  # doctest: +NORMALIZE_WHITESPACE
                       id favourite
    cat1  cat2  cat3
    True  False False   0     green
          True  False   1       red
          False False   2       red
    False True  False   3    yellow
          False True    4      blue
    """
    df = _contents_to_indicators(contents)
    cat_names = list(df.columns)
    if id_column in df.columns:
        raise ValueError('A category cannot be named %r' % id_column)

    if data is not None:
        if set(df.columns).intersection(data.columns):
            raise ValueError('Data columns overlap with category names')
        if id_column in data.columns:
            raise ValueError('data cannot contain a column named %r' %
                             id_column)
        not_in_data = df.drop(data.index, axis=0, errors='ignore')
        if len(not_in_data):
            raise ValueError('Found identifiers in contents that are not in '
                             'data: %r' % not_in_data.index.values)
        df = df.reindex(index=data.index).fillna(False)
        df = _concat([data, df], axis=1)
    df.index.name = id_column
    return df.reset_index().set_index(cat_names)


### SPEC

# TODO: Test use of CategorizedData and CategorizedCounts passed to plot()


# Minimal data representation is:
# * data with unique index
# * indexed binary-packed masks
# * category names
# * a function to reorder categories by operating on binary-packed masks

def _pack_bitmask(X):
    X = pd.DataFrame(X)
    if X.shape[1] <= 8:
        return np.packbits(X.values.astype(bool), axis=1) >> (8 - X.shape[1])
    out = 0
    for i, (_, col) in enumerate(X.items()):
        out *= 2
        out += col
    return out


class CategorizedData:
    """Represents data where each sample is assigned to one or more categories

    Parameters
    ----------
    categories : list of str, or DataFrame-like
        If a list of str, this should be names of boolean category indicator
        columns in `data`. Otherwise, this should be a boolean DataFrame whose
        column names indicate categories and do not have any column names in
        common with `data`.

    data : DataFrame-like, or None

    Attributes
    ----------
    categories : list of str
    data : DataFrame
    """

    def __init__(self, indicators, data=None, category_names=None):
        indicators = pd.DataFrame(indicators)
        if indicators.shape[1] == 1 and category_names is not None and indicators.dtypes[0].kind in 'iu':
            # already a bit mask?
            if indicators.max() >= 2 ** len(category_names) or indicators.max() < 0:
                raise ValueError("Got something that looked like a bit mask, "
                                 "but its values were out of "
                                 "[0, 2 ** n_categories - 1]")
            indicators = indicators.loc[:, 0]
        else:
            if category_names is not None:
                indicators.columns = category_names
            else:
                category_names = indicator.columns

            if not all(dtype.kind == 'b' for dtype in indicators.dtypes) and not all(
                set([True, False]) >= set(indicators[col].unique()) for col in indicators.columns):
                raise ValueError('The indicators must all be boolean')
                
            indicators = _pack_bitmask(indicators)
        indicators.index = getattr(data, 'index', None)
        self.indicator_bitmask = indicators
        self.data = data
        self.category_names = category_names

    @classmethod
    def from_indicator_columns(cls, indicators, data=None):
        """

        Pulls out category columns from data
        """
        if isinstance(indicators[0], (str, int)):
            assert data is not None
            assert all(column in data for column in indicators)
            indicators = data[indicators]

        return cls(indicators=indicators, data=data)

    @classmethod
    def from_memberships(cls, memberships, data=None):
        indicators = _memberships_to_indicators(memberships)
        if data is None:
            data = indicators[[]]
        return cls(data=data, indicators=indicators)

    @classmethod
    def from_memberships_str(cls, memberships, data=None,
                             sep=re.compile(r'(?u)[^\w\ ]')):
        if isinstance(memberships, str):
            memberships = data[memberships]
        if hasattr(sep, 'match'):
            lists = pd.Series(memberships).apply(lambda x: sep.split)
        else:
            lists = pd.Series(memberships).str.split(sep)
        return cls.from_memberships(lists, data)

    @classmethod
    def from_contents(cls, contents, data=None):
        indicators = _contents_to_indicators(contents)
        if data is None:
            data = indicators[[]]
        return cls(data=data, indicators=indicators)

    def to_frame_indexed_by_indicators(self):
        """Represent self as a DataFrame indexed by category indicators
        """
        return self.data.set_index(self._get_unpack_map().loc[self.indicator_bitmask])

    def _get_unpack_map(self):
        assert len(self.category_names) < 8
        return pd.DataFrame(np.unpackbits(self.indicator_bitmask).reshape(-1, 8).astype(bool),
                            columns=self.category_names)

    def reorder_categories(self, new_order):
        """Create a new CategorizedData with the same data but reordered categories
        """
        new_bitmask = _pack_bitmask(self._get_unpack_map()[list(new_order)])
        return type(self)(indicators=new_bitmask, data=self.data,
                          category_names=new_order)

    def get_counts(self, weight=None):
        """
        Parameters
        ----------
        weight : str
            Column to use as weight
        """
        gb = self.frame.groupby(self.indicator_bitmask)
        if weight is None:
            return CategorizedCounts(gb.size())
        else:
            return CategorizedCounts(gb[weight].sum())


class CategorizedCounts:

    def __init__(self, counts):
        # TODO: handle indicator bitmask
        assert all(set([True, False]) >= set(level)
                   for level in counts.index.levels)
        assert counts.index.is_unique
        self.counts = counts

    def get_totals(self):
        agg = self.counts
        out = [agg[agg.index.get_level_values(name).values.astype(bool)].sum()
               for name in agg.index.names]
        out = pd.Series(out, index=agg.index.names)
        return out

    def sort(self, sort_by='degree', sort_categories_by=None,
             inplace=False):
        if not inplace:
            out = type(self)(self.counts.copy())
            out.sort(
                sort_by=sort_by, sort_categories_by=sort_categories_by,
                inplace=True)
            return out

        if sort_categories_by is None:
            pass
        elif sort_categories_by == 'cardinality':
            totals = self.get_totals()
            totals.sort_values(ascending=False, inplace=True)
            self.counts = self.counts.reorder_levels(totals.index.values)
        else:
            raise ValueError('Unknown sort_categories_by: %r' %
                             sort_categories_by)

        if sort_by == 'cardinality':
            self.counts.sort_values(ascending=False, inplace=True)
        elif sort_by == 'degree':
            comb = itertools.combinations
            o = pd.DataFrame([{name: True for name in names}
                              for i in range(self.counts.index.nlevels + 1)
                              for names in comb(self.counts.index.names, i)],
                             columns=self.counts.index.names)
            o.fillna(False, inplace=True)
            o = o.astype(bool)
            o.set_index(self.counts.index.names, inplace=True)
            self.counts = self.counts.reindex(index=o.index, copy=False)
        else:
            raise ValueError('Unknown sort_by: %r' % sort_by)


class OldVennData:
    def __init__(self, df, key_fields=None, category_fields=None):
        self._df = self._check_df(df)

    def _check_df(self, df):
        # TODO
        return df

    @classmethod
    def from_memberships(cls, memberships, data=None):
        """Build data from the category membership of each element

        Parameters
        ----------
        memberships : sequence of collections of strings
            Each element corresponds to a data point, indicating the sets it is
            a member of.  Each set is named by a string.
        data : Series-like or DataFrame-like, optional
            If given, the index of set memberships is attached to this data.
            It must have the same length as `memberships`.
            If not given, the series will contain the value 1.

        Returns
        -------
        VennData
        """
        return cls(from_memberships(memberships, data))

    @classmethod
    def from_contents(cls, contents, data=None):
        """Build data from category listings

        Parameters
        ----------
        contents : Mapping of strings to sets
            Map values be sets of identifiers (int or string).
        data : DataFrame, optional
            If provided, this should be indexed by the identifiers used in
            `contents`.

        Returns
        -------
        VennData
        """
        return cls(from_contents(contents, data))

    def _get_cat_mask(self):
        return self._df.index.to_frame(index=False)

    def _get_data(self):
        return self._df.reset_index()

    def get_intersection(self, categories, inclusive=False):
        """Retrieve elements that are in all the given categories

        Parameters
        ----------
        categories : collection of strings
        inclusive : bool
            If False (default), do not include elements that are in additional
            categories.
        """
        categories = list(categories)
        cat_mask = self._get_cat_mask()
        # XXX: More efficient with a groupby?
        mask = cat_mask[categories].all(axis=1)
        if not inclusive:
            mask &= ~cat_mask.drop(categories, axis=1).any(axis=1)
        return self._get_data()[mask]

    def count_intersection(self, categories, inclusive=False):
        """Count the number of elements in all the given categories

        Parameters
        ----------
        categories : collection of strings
        inclusive : bool
            If False (default), do not include elements that are in additional
            categories.
        """
