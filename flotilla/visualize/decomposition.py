from __future__ import division

from collections import defaultdict
from itertools import cycle
import math

from matplotlib.gridspec import GridSpec, GridSpecFromSubplotSpec
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from .color import deep
from .generic import violinplot


class DecompositionViz(object):
    """
    Plots the reduced space from a decomposed dataset. Does not perform any
    reductions of its own
    """

    def __init__(self, reduced_space, components_,
                 explained_variance_ratio_,
                 feature_renamer=None, groupby=None,
                 singles=None, pooled=None, outliers=None,
                 featurewise=False,
                 order=None, violinplot_kws=None,
                 data_type='expression', label_to_color=None,
                 label_to_marker=None,
                 scale_by_variance=True, x_pc='pc_1',
                 y_pc='pc_2', n_vectors=20, distance='L1',
                 n_top_pc_features=50, max_char_width=30):
        """Plot the results of a decomposition visualization

        Parameters
        ----------
        reduced_space : pandas.DataFrame
            A (n_samples, n_dimensions) DataFrame of the post-dimensionality
            reduction data
        components_ : pandas.DataFrame
            A (n_features, n_dimensions) DataFrame of how much each feature
            contributes to the components (trailing underscore to be
            consistent with scikit-learn)
        explained_variance_ratio_ : pandas.Series
            A (n_dimensions,) Series of how much variance each component
            explains. (trailing underscore to be consistent with scikit-learn)
        feature_renamer : function, optional
            A function which takes the name of the feature and renames it,
            e.g. from an ENSEMBL ID to a HUGO known gene symbol. If not
            provided, the original name is used.
        groupby : mapping function | dict, optional
            A mapping of the samples to a label, e.g. sample IDs to
            phenotype, for the violinplots. If None, all samples are treated
            the same and are colored the same.
        singles : pandas.DataFrame, optional
            For violinplots only. If provided and 'plot_violins' is True,
            will plot the raw (not reduced) measurement values as violin plots.
        pooled : pandas.DataFrame, optional
            For violinplots only. If provided, pooled samples are plotted as
            black dots within their label.
        outliers : pandas.DataFrame, optional
            For violinplots only. If provided, outlier samples are plotted as
            a grey shadow within their label.
        featurewise : bool, optional
            If True, then the "samples" are features, e.g. genes instead of
            samples, and the "features" are the samples, e.g. the cells
            instead of the gene ids. Essentially, the transpose of the
            original matrix. If True, then violins aren't plotted. (default
            False)
        order : list-like
            The order of the labels for the violinplots, e.g. if the data is
            from a differentiation timecourse, then this would be the labels
            of the phenotypes, in the differentiation order.
        violinplot_kws : dict
            Any additional parameters to violinplot
        data_type : 'expression' | 'splicing', optional
            For violinplots only. The kind of data that was originally used
            for the reduction. (default 'expression')
        label_to_color : dict, optional
            A mapping of the label, e.g. the phenotype, to the desired
            plotting color (default None, auto-assigned with the groupby)
        label_to_marker : dict, optional
            A mapping of the label, e.g. the phenotype, to the desired
            plotting symbol (default None, auto-assigned with the groupby)
        scale_by_variance : bool, optional
            If True, scale the x- and y-axes by their explained_variance_ratio_
            (default True)
        {x,y}_pc : str, optional
            Principal component to plot on the x- and y-axis. (default "pc_1"
            and "pc_2")
        n_vectors : int, optional
            Number of vectors to plot of the principal components. (default 20)
        distance : 'L1' | 'L2', optional
            The distance metric to use to plot the vector lengths. L1 is
            "Cityblock", i.e. the sum of the x and y coordinates, and L2 is
            the traditional Euclidean distance. (default "L1")
        n_top_pc_features : int, optional
            THe number of top features from the principal components to plot.
            (default 50)
        max_char_width : int, optional
            Maximum character width of a feature name. Useful for crazy long
            feature IDs like MISO IDs
        """
        self.reduced_space = reduced_space
        self.components_ = components_
        self.explained_variance_ratio_ = explained_variance_ratio_

        self.singles = singles
        self.pooled = pooled
        self.outliers = outliers

        self.groupby = groupby
        self.order = order
        self.violinplot_kws = violinplot_kws if violinplot_kws is not None \
            else {}
        self.data_type = data_type
        self.label_to_color = label_to_color
        self.label_to_marker = label_to_marker
        self.n_vectors = n_vectors
        self.x_pc = x_pc
        self.y_pc = y_pc
        self.pcs = (self.x_pc, self.y_pc)
        self.distance = distance
        self.n_top_pc_features = n_top_pc_features
        self.featurewise = featurewise
        self.feature_renamer = feature_renamer
        self.max_char_width = max_char_width

        if self.groupby is None:
            self.groupby = dict.fromkeys(self.reduced_space.index, 'all')
        self.grouped = self.reduced_space.groupby(self.groupby, axis=0)

        if self.label_to_color is None:
            colors = iter(sns.color_palette('husl',
                                            n_colors=len(self.grouped)))
            def color_factory():
                return colors.next()

            self.label_to_color = defaultdict(color_factory)

        if self.label_to_marker is None:
            markers = cycle(['o', '^', 's', 'v', '*', 'D', 'h'])

            def marker_factory():
                return markers.next()

            self.label_to_marker = defaultdict(marker_factory)

        if order is not None:
            self.color_ordered = [self.label_to_color[x] for x in self.order]
        else:
            self.color_ordered = [self.label_to_color[x] for x in
                                  self.grouped.groups]

        self.loadings = self.components_.ix[[self.x_pc, self.y_pc]]

        # Get the explained variance
        if explained_variance_ratio_ is not None:
            self.vars = explained_variance_ratio_[[self.x_pc, self.y_pc]]
        else:
            self.vars = pd.Series([1., 1.], index=[self.x_pc, self.y_pc])

        if scale_by_variance:
            self.loadings = self.loadings.multiply(self.vars, axis=0)

        # sort features by magnitude/contribution to transformation
        reduced_space = self.reduced_space[[self.x_pc, self.y_pc]]
        farthest_sample = reduced_space.apply(np.linalg.norm, axis=0).max()
        whole_space = self.loadings.apply(np.linalg.norm).max()
        scale = .25 * farthest_sample / whole_space
        self.loadings *= scale

        ord = 2 if self.distance == 'L2' else 1
        self.magnitudes = self.loadings.apply(np.linalg.norm, ord=ord)
        self.magnitudes.sort(ascending=False)

        self.top_features = set([])
        self.pc_loadings_labels = {}
        self.pc_loadings = {}
        for pc in self.pcs:
            x = self.components_.ix[pc].copy()
            x.sort(ascending=True)
            half_features = int(self.n_top_pc_features / 2)
            if len(x) > self.n_top_pc_features:
                a = x[:half_features]
                b = x[-half_features:]
                labels = np.r_[a.index, b.index]
                self.pc_loadings[pc] = np.r_[a, b]
            else:
                labels = x.index
                self.pc_loadings[pc] = x

            self.pc_loadings_labels[pc] = labels
            self.top_features.update(labels)

    def plot(self, ax=None, title='', plot_violins=False,
                 show_point_labels=False,
                 show_vectors=True,
                 show_vector_labels=True,
                 markersize=10, legend=True, bokeh=False, metadata=None):

        if bokeh:
            self._plot_bokeh(metadata, title)
        else:
            gs_x = 14
            gs_y = 12

            if ax is None:
                self.reduced_fig, ax = plt.subplots(1, 1, figsize=(20, 10))
                gs = GridSpec(gs_x, gs_y)

            else:
                gs = GridSpecFromSubplotSpec(gs_x, gs_y, ax.get_subplotspec())
                self.reduced_fig = plt.gcf()

            ax_components = plt.subplot(gs[:, :5])
            ax_loading1 = plt.subplot(gs[:, 6:8])
            ax_loading2 = plt.subplot(gs[:, 10:14])

            self.plot_samples(show_point_labels=show_point_labels,
                              title=title, show_vectors=show_vectors,
                              show_vector_labels=show_vector_labels,
                              markersize=markersize, legend=legend,
                              ax=ax_components)
            self.plot_loadings(pc=self.x_pc, ax=ax_loading1)
            self.plot_loadings(pc=self.y_pc, ax=ax_loading2)
            sns.despine()
            self.reduced_fig.tight_layout()

            if plot_violins and not self.featurewise and self.singles is not None:
                self.plot_violins()
            return self

    def _plot_bokeh(self, metadata=None, title=''):
        metadata = metadata if metadata is not None else pd.DataFrame(
            index=self.reduced_space.index)
        # Clean alias
        import bokeh.plotting as bk
        from bokeh.plotting import ColumnDataSource, figure, show
        from bokeh.models import HoverTool

        # Plots can be displayed inline in an IPython Notebook
        bk.output_notebook(force=True)


        # Create a set of tools to use
        TOOLS = "pan,wheel_zoom,box_zoom,reset,hover"

        x = self.reduced_space[self.x_pc]
        y = self.reduced_space[self.y_pc]

        radii = np.ones(x.shape)

        colors = self.reduced_space.index.map(
            lambda x: self.label_to_color[self.groupby[x]])
        sample_ids = self.reduced_space.index

        data = dict(
            (col, metadata[col][self.reduced_space.index]) for
            col in metadata)
        tooltips = [('sample_id', '@sample_ids')]
        tooltips.extend([(k, '@{}'.format(k)) for k in data.keys()])

        data.update(dict(
            x=x,
            y=y,
            colors=colors,
            sample_ids=sample_ids
        ))

        source = ColumnDataSource(
            data=data
        )

        p = figure(title=title, tools=TOOLS)

        p.circle(x, y, radius=radii, source=source,
                 fill_color=colors, fill_alpha=0.6, line_color=None)
        hover = p.select(dict(type=HoverTool))
        hover.tooltips = tooltips

        show(p)


    def shorten(self, x):
        if len(x) > self.max_char_width:
            return '{}...'.format(x[:self.max_char_width])
        else:
            return x

    def plot_samples(self, show_point_labels=True,
                     title='DataFramePCA', show_vectors=True,
                     show_vector_labels=True, markersize=10,
                     three_d=False, legend=True, ax=None):

        """
        Given a pandas dataframe, performs DataFramePCA and plots the results in a
        convenient single function.

        Parameters
        ----------
        groupby : groupby
            How to group the samples by color/label
        label_to_color : dict
            Group labels to a matplotlib color E.g. if you've already chosen
            specific colors to indicate a particular group. Otherwise will
            auto-assign colors
        label_to_marker : dict
            Group labels to matplotlib marker
        title : str
            title of the plot
        show_vectors : bool
            Whether or not to draw the vectors indicating the supporting
            principal components
        show_vector_labels : bool
            whether or not to draw the names of the vectors
        show_point_labels : bool
            Whether or not to label the scatter points
        markersize : int
            size of the scatter markers on the plot
        text_group : list of str
            Group names that you want labeled with text
        three_d : bool
            if you want hte plot in 3d (need to set up the axes beforehand)

        Returns
        -------
        For each vector in data:
        x, y, marker, distance
        """
        if ax is None:
            ax = plt.gca()

        # Plot the samples
        for name, df in self.grouped:
            color = self.label_to_color[name]
            marker = self.label_to_marker[name]
            x = df[self.x_pc]
            y = df[self.y_pc]
            ax.plot(x, y, color=color, marker=marker, linestyle='None',
                    label=name, markersize=markersize, alpha=0.75,
                    markeredgewidth=.1)
            try:
                if not self.pooled.empty:
                    pooled_ids = x.index.intersection(self.pooled.index)
                    pooled_x, pooled_y = x[pooled_ids], y[pooled_ids]
                    ax.plot(pooled_x, pooled_y, 'o', color=color, marker=marker,
                            markeredgecolor='k', markeredgewidth=2,
                            label='{} pooled'.format(name),
                            markersize=markersize, alpha=0.75)
            except AttributeError:
                pass
            try:
                if not self.outliers.empty:
                    outlier_ids = x.index.intersection(self.outliers.index)
                    outlier_x, outlier_y = x[outlier_ids], y[outlier_ids]
                    ax.plot(outlier_x, outlier_y, 'o', color=color,
                            marker=marker,
                            markeredgecolor='lightgrey', markeredgewidth=5,
                            label='{} outlier'.format(name),
                            markersize=markersize, alpha=0.75)
            except AttributeError:
                pass
            if show_point_labels:
                for args in zip(x, y, df.index):
                    ax.text(*args)

        # Plot vectors, if asked
        if show_vectors:
            for vector_label in self.magnitudes[:self.n_vectors].index:
                x, y = self.loadings[vector_label]
                ax.plot([0, x], [0, y], color='k', linewidth=1)
                if show_vector_labels:
                    x_offset = math.copysign(5, x)
                    y_offset = math.copysign(5, y)
                    horizontalalignment = 'left' if x > 0 else 'right'
                    if self.feature_renamer is not None:
                        renamed = self.feature_renamer(vector_label)
                    else:
                        renamed = vector_label
                    ax.annotate(renamed, (x, y),
                                textcoords='offset points',
                                xytext=(x_offset, y_offset),
                                horizontalalignment=horizontalalignment)

        # Label x and y axes
        ax.set_xlabel(
            'Principal Component {} (Explains {:.2f}% Of Variance)'.format(
                str(self.x_pc), 100 * self.vars[self.x_pc]))
        ax.set_ylabel(
            'Principal Component {} (Explains {:.2f}% Of Variance)'.format(
                str(self.y_pc), 100 * self.vars[self.y_pc]))
        ax.set_title(title)

        if legend:
            ax.legend()
        sns.despine()

    def plot_loadings(self, pc='pc_1', n_features=50, ax=None):
        loadings = self.pc_loadings[pc]
        labels = self.pc_loadings_labels[pc]

        if ax is None:
            ax = plt.gca()

        # import pdb; pdb.set_trace()
        x = loadings
        y = np.arange(loadings.shape[0])

        ax.scatter(x, y, color=deep[0])
        ax.set_ylim(-.5, y.max()+.5)

        ax.set_yticks(np.arange(max(loadings.shape[0], n_features)))
        ax.set_title("Component " + pc)

        x_offset = max(loadings) * .05
        ax.set_xlim(left=loadings.min() - x_offset,
                    right=loadings.max() + x_offset)

        if self.feature_renamer is not None:
            labels = map(self.feature_renamer, labels)
        else:
            labels = labels

        labels = map(self.shorten, labels)
        # ax.set_yticklabels(map(shorten, labels))
        ax.set_yticklabels(labels)
        for lab in ax.get_xticklabels():
            lab.set_rotation(90)
        sns.despine(ax=ax)

    def plot_explained_variance(self, title="PCA explained variance"):
        """If the reducer is a form of PCA, then plot the explained variance
        ratio by the components.
        """
        # Plot the explained variance ratio
        assert self.explained_variance_ratio_ is not None
        import matplotlib.pyplot as plt
        import seaborn as sns

        fig, ax = plt.subplots()
        ax.plot(self.explained_variance_ratio_, 'o-')

        xticks = np.arange(len(self.explained_variance_ratio_))
        ax.set_xticks(xticks)
        ax.set_xticklabels(xticks + 1)
        ax.set_xlabel('Principal component')
        ax.set_ylabel('Fraction explained variance')
        ax.set_title(title)
        sns.despine()

    def plot_violins(self):
        """Make violinplots of each feature

        Must be called after plot_samples because it depends on the existence
        of the "self.magnitudes" attribute.
        """
        ncols = 4
        nrows = 1
        vector_labels = list(set(self.magnitudes[:self.n_vectors].index.union(
            pd.Index(self.top_features))))
        while ncols * nrows < len(vector_labels):
            nrows += 1
        self.violins_fig, axes = plt.subplots(nrows=nrows, ncols=ncols,
                                              figsize=(4 * ncols, 4 * nrows))

        if self.feature_renamer is not None:
            renamed_vectors = map(self.feature_renamer, vector_labels)
        else:
            renamed_vectors = vector_labels
        labels = [(y, x) for (y, x) in sorted(zip(renamed_vectors,
                                                  vector_labels))]

        for (renamed, feature_id), ax in zip(labels, axes.flat):
            singles = self.singles[feature_id] if self.singles is not None \
                else None
            pooled = self.pooled[feature_id] if self.pooled is not None else \
                None
            outliers = self.outliers[feature_id] if self.outliers is not None \
                else None

            if isinstance(feature_id, tuple):
                feature_id = feature_id[0]
            if len(feature_id) > 25:
                feature_id = feature_id[:25] + '...'
            if renamed != feature_id:
                title = '{}\n{}'.format(feature_id, renamed)
            else:
                title = feature_id
            singles.name = renamed
            pooled.name = renamed
            outliers.name = renamed
            # import pdb; pdb.set_trace()
            violinplot(singles, pooled_data=pooled, outliers=outliers,
                       groupby=self.groupby, color_ordered=self.color_ordered,
                       order=self.order, title=title,
                       ax=ax, data_type=self.data_type,
                       **self.violinplot_kws)

            if self.data_type == 'splicing':
                ax.set_ylabel('$\Psi$')
                ax.set_ylim(0, 1)
            elif self.data_type == 'expression':
                ax.set_ylabel('Expression')
            else:
                ax.set_ylabel('')

        # Clear any unused axes
        for ax in axes.flat:
            # Check if the plotting space is empty
            if len(ax.collections) == 0 or len(ax.lines) == 0:
                ax.axis('off')
        self.violins_fig.tight_layout()
