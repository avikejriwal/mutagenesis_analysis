#!/usr/bin/env python
"""
Suite of functions written for generating figures associated with deep
mutagenesis library selection experiments
"""

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib.offsetbox import AnchoredText
from matplotlib.patches import Rectangle, Ellipse
from scipy.stats import norm

from plasmid_map import Gene
from sequencing_data import SequencingData
from fitness_analysis import (
    get_pairs,
    heatmap_masks,
    filter_fitness_read_noise,
    gaussian_significance,
)


def respine(ax: matplotlib.axes) -> None:
    """
    Set the edges of the axes to be solid gray

    Parameters
    ----------
        ax : Axes
            Axes with heatmap plot

    Returns
    -------
        None
    """
    for _, spine in ax.spines.items():
        spine.set_visible(True)
        spine.set_edgecolor("darkslategray")
        spine.set_lw(0.4)


def histogram_mutation_counts(sequencing_data: SequencingData) -> matplotlib.figure:
    """
    Generate Figure of histograms plotting distribution of number of counts
    found per amino acid mutation

    Parameters
    ----------
    sequencing_data : SequencingData
        Object providing data for number of counts found per sample

    Returns
    -------
    fig : matplotlib.figure
        Figure with each sample plotted on a different Subplot
    """
    counts = sequencing_data.counts
    num_plots = len(counts)
    height = num_plots * 1.8

    fig, axes = plt.subplots(
        nrows=num_plots, figsize=(5, height), constrained_layout=True, sharey=True
    )
    fig.suptitle("Distribution of counts for all amino acids")

    for i, sample in enumerate(counts):
        # * these indices are specific to the mature TEM-1 protein
        # * would need to be changed if you used a different gene
        counts_values = counts[sample].loc[23:285, :"Y"]
        num_missing = counts_values.lt(1).sum().sum() - counts_values.shape[0]
        with np.errstate(divide="ignore"):
            log_values = counts_values.where(
                counts_values.lt(1), np.log10(counts_values)
            )
        log_values = log_values.where(log_values != 0.01, np.nan).values.flatten()
        # * total number of mutants specific to TEM-1 library
        pct_missing = num_missing / 4997
        ax = axes[i]
        ax.hist(
            log_values,
            bins=40,
            color="gray",
            edgecolor="black",
            range=(np.nanmin(log_values), np.nanmax(log_values)),
        )

        ax.set_ylabel("number of amino acid mutations", fontsize=7)
        ax.set_xlabel("counts per amino acid mutation ($log_{10}$)", fontsize=7)

        ax.spines.top.set_visible(False)
        ax.spines.right.set_visible(False)
        ax.tick_params(direction="in", labelsize=7)
        ax.set_title(sample, fontsize=12, fontweight="bold")

        counts_values = counts_values.query("@counts_values.ge(1)").values.flatten()
        counts_values = np.extract(np.isfinite(counts_values), counts_values)
        mean, _ = norm.fit(counts_values)
        text_mean = (
            f"missing: {num_missing} ({pct_missing:.2%})\nmean: {round(mean, 3)}"
        )
        annot_box = AnchoredText(
            text_mean, loc="upper right", pad=0.8, prop=dict(size=6), frameon=True
        )
        ax.add_artist(annot_box)
    return fig


# ! Unused function
def heatmap_missing_mutations(
    df: pd.DataFrame, ax=None, cbar_ax=None, orientation="vertical"
) -> matplotlib.axes:
    """
    Plot a heatmap showing positions in the library where mutants are missing

    Parameters
    ----------
    df : pandas.DataFrame
        Data matrix to be drawn
    ax : AxesSubplot
        Axes to draw the heatmap
    cbar_ax : AxesSubplot
        Axes to draw the colorbar
    orientation : str, optional
        Whether to draw "horizontal" or "vertical", by default "vertical"


    Returns
    -------
    ax : AxesSubplot
    """
    if ax is None:
        ax = plt.subplot()
    # convert data table from integer counts to a binary map
    df_missing = df.ge(5)
    df_missing = df_missing.loc[:, :"Y"]
    if orientation == "horizontal":
        df_missing = df_missing.T

    im = ax.imshow(df_missing, cmap="Blues")

    # add colorbar index
    cbar = plt.colorbar(
        im,
        cax=cbar_ax,
        orientation=orientation,
        boundaries=[0, 0.5, 1],
        ticks=[0.25, 0.75],
    )
    cbar.ax.tick_params(bottom=False, right=False)
    if orientation == "horizontal":
        cbar.ax.set_xticklabels(["missing", "present"])
        cbar.ax.set_aspect(0.08)
    else:
        cbar.ax.set_yticklabels(["missing", "present"], rotation=-90, va="center")
        cbar.ax.set_aspect(12.5)

    return ax


def heatmap_wrapper(
    df: pd.DataFrame,
    name: str,
    dataset: str,
    gene: Gene,
    ax: matplotlib.axes = None,
    cbar: bool = False,
    cbar_ax: matplotlib.axes = None,
    vmin: float = -2.0,
    vmax: float = 2.0,
    fitness_cmap: str = "vlag",
    orientation: str = "horizontal",
) -> matplotlib.axes:
    """
    Function wrapper for preferred heatmap aesthetic settings

    Parameters
    ----------
    df : pd.DataFrame
        Matrix to be plotted
    name : str
        Sample name for axes labeling
    dataset : str
        Type of data ("counts" or "fitness")
    gene : Gene
        Gene object to provide residue numbering
    ax : matplotlib.axes, optional
        Axes on which to draw the data, by default None
    cbar : bool, optional
        Whether to draw a colorbar or not, by default False
    cbar_ax : matplotlib.axes, optional
        Axes on which to draw the colorbar, by default None
    vmin : float, optional
        For fitness data, vmin parameter passed to sns.heatmap, by default -2.0
    vmax : float, optional
        For fitness data, vmax parameter passed to sns.heatmap, by default 2.0
    fitness_cmap : str, optional
        Colormap to use for fitness heatmap, by default "vlag"
    orientation : str, optional
        Whether to draw heatmaps vertically or horizontally, by default "horizontal"

    Returns
    -------
    h : matplotlib.axes
        Axes object with the heatmap
    """
    if dataset == "counts":
        with np.errstate(divide="ignore"):
            df = df.where(df.lt(1), np.log10(df))
            cmap = "Blues"
            vmin = None
            vmax = None
    elif dataset == "fitness":
        cmap = fitness_cmap

    xticklabels, yticklabels = 1, 10
    df_wt = heatmap_masks(gene)

    if orientation == "horizontal":
        df_wt = df_wt.T
        df = df.T
        xticklabels, yticklabels = yticklabels, xticklabels

    h = sns.heatmap(
        df,
        square=True,
        xticklabels=xticklabels,
        yticklabels=yticklabels,
        cbar=cbar,
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        linecolor="slategray",
        linewidths=0.2,
        clip_on=True,
        ax=ax,
        cbar_ax=cbar_ax,
    )
    h.set_facecolor("white")
    h.set_anchor("NW")

    # * adjust ticks
    h.tick_params(
        left=False,
        bottom=False,
        top=False,
        right=False,
        labelbottom=False,
        labelleft=False,
        rotation=0,
        labelsize=3,
        length=0,
        pad=1,
    )
    h.tick_params(axis="y", labelsize=4)
    if orientation == "horizontal":
        h.tick_params(labelsize=1.5)
        h.tick_params(axis="x", rotation=90, labelsize=2)

    # * set title
    if orientation == "vertical":
        ax.set_title(name, fontweight="bold", fontsize=8, pad=2)
    elif orientation == "horizontal":
        ax.set_ylabel(name, fontweight="bold", fontsize=6, labelpad=2)

    # * draw and label wild-type patches
    for j, i in np.asarray(np.where(df_wt)).T:
        h.add_patch(Rectangle((i, j), 1, 1, fill=True, color="slategray", ec=None))
        j += 0.5
        if orientation == "horizontal":
            rotation = 90
            fontsize = 2
        elif orientation == "vertical":
            rotation = 0
            fontsize = 4
        h.text(
            i,
            j,
            "/",
            color="white",
            va="center",
            fontsize=fontsize,
            fontfamily="monospace",
            rotation=rotation,
            clip_on=True,
        )
    respine(h)
    # * reformat coordinate labeler
    if orientation == "vertical":

        def format_coord(x, y):
            x = np.floor(x).astype("int")
            y = np.floor(y).astype("int")
            residue = df.columns[x]
            pos = df.index[y]
            fitness_score = df.loc[pos, residue].round(4)
            return f"position: {pos}, residue: {residue}, fitness: {fitness_score}"

    elif orientation == "horizontal":

        def format_coord(x, y):
            x = np.floor(x).astype("int")
            y = np.floor(y).astype("int")
            pos = df.columns[x]
            residue = df.index[y]
            fitness_score = df.loc[residue, pos].round(4)
            return f"position: {pos}, residue: {residue}, fitness: {fitness_score}"

    ax.format_coord = format_coord
    return h


def heatmap_draw(
    counts_dict: dict,
    fitness_dict: dict,
    dataset: str,
    gene: Gene,
    read_threshold: int = 1,
    vmin: float = -2.0,
    vmax: float = 2.0,
    fitness_cmap: str = "vlag",
    orientation: str = "horizontal",
) -> matplotlib.figure:
    """
    Draw a heatmap figure of a dataset
    # TODO: Consider re-adding figure to make a missing chart, but perhaps not really necessary

    Parameters
    ----------
    counts_dict : dict
        Reference with counts dataframes for all samples
    fitness_dict : dict
        Reference with fitness dataframes for all samples
    dataset : str
        Whether to draw a heatmap for raw (log-transformed) counts or fitness values
    gene : Gene
        Gene object that provides residue numbering
    read_threshold : int
        Minimum number of reads for fitness value to be considered valid, by default 1
    vmin : float, optional
        For fitness data, vmin parameter passed to sns.heatmap, by default -2.0
    vmax : float, optional
        For fitness data, vmax parameter passed to sns.heatmap, by default 2.0
    fitness_cmap : str, optional
        Colormap to use for fitness heatmap, by default "vlag"
    orientation : str, optional
        Whether to draw heatmaps vertically or horizontally, by default "horizontal"

    Returns
    -------
    fig : matplotlib.figure
    """

    # * determine parameters for plotting function based on figure type
    params_counts = {
        "df_dict": counts_dict,
        "num_columns": len(counts_dict),
        "num_rows": 1,
        "suptitle": "Raw counts of mutations ($log_{10}$)",
    }
    params_fitness = {
        "df_dict": fitness_dict,
        "num_columns": len(fitness_dict),
        "num_rows": 1,
        "suptitle": "Fitness values",
    }
    if dataset == "counts":
        df_dict, num_columns, num_rows, suptitle = params_counts.values()
    elif dataset == "fitness":
        df_dict, num_columns, num_rows, suptitle = params_fitness.values()
        # * will use filtered data here, but default is to not filter (i.e. read_threshold=1)
        df_dict = {
            key: filter_fitness_read_noise(
                key, counts_dict, fitness_dict, gene, read_threshold=read_threshold
            )
            for key in sorted(fitness_dict)
        }

    if orientation == "horizontal":
        num_columns, num_rows = num_rows, num_columns
        cbar_location = "bottom"
    else:
        cbar_location = "right"

    fig, axs = plt.subplots(
        num_rows,
        num_columns,
        figsize=(5, 12),
        dpi=300,
        layout="compressed",
        sharex=True,
        sharey=True,
    )
    fig.suptitle(suptitle, fontweight="bold")

    # * plot each data one by one
    for i, sample in enumerate(sorted(df_dict)):
        data = df_dict[sample]
        # * function-provided styling for heatmaps
        if dataset == "counts":
            heatmap_wrapper(
                data,
                name=sample,
                gene=gene,
                dataset=dataset,
                ax=axs[i],
                orientation=orientation,
            )
        elif dataset == "fitness":
            heatmap_wrapper(
                data,
                name=sample,
                gene=gene,
                dataset=dataset,
                ax=axs[i],
                vmin=vmin,
                vmax=vmax,
                fitness_cmap=fitness_cmap,
                orientation=orientation,
            )
    if orientation == "horizontal":
        # * re-size Figure down to height of all subplots combined after plotting
        height = 0
        for ax in fig.axes:
            ax.tick_params(labelleft=True)
            height += (
                ax.get_tightbbox().transformed(fig.dpi_scale_trans.inverted()).height
            )
        fig.axes[0].tick_params(labeltop=True)
        fig.set_figheight(height + 1)
        # * adjust subplot spacing
        pad = fig.get_layout_engine().get()["hspace"] / 2

    elif orientation == "vertical":
        for ax in fig.axes:
            ax.tick_params(labelbottom=True)
        fig.axes[0].tick_params(labelleft=True)
        # * re-size Figure down
        fig.set_figheight(fig.get_tightbbox().height)
        # * adjust sutplob spacing
        pad = fig.get_layout_engine().get()["wspace"] / 2

    # * add colorbar
    cbar = fig.colorbar(
        axs[0].collections[0],
        ax=fig.axes,
        shrink=0.2,
        fraction=0.1,
        pad=pad,
        anchor="NW",
        location=cbar_location,
        use_gridspec=True,
    )
    cbar.ax.spines["outline"].set_lw(0.4)
    cbar.ax.tick_params(right=False, left=False, labelsize=4, length=0, pad=3)
    return fig


def relabel_axis(
    fig: matplotlib.figure, gene: Gene, orientation: str = "horizontal"
) -> None:
    """
    Here we relabel the position-axis of the heatmap figure to use the Ambler numbering system.

    Parameters
    ----------
    fig : matplotlib.figure
        Parent figure of all the heatmap axes
    gene : Gene
        Gene object that holds a numbering system attribute
    orientation : str, optional
        Whether the heatmaps are drawn horizontally or vertically, by default "horizontal"

    Returns
    -------
    None
    """
    # * df for adjusting interactive hover annotations
    df_wt = heatmap_masks(gene)
    rows, cols = df_wt.shape
    if orientation == "vertical":
        fig.axes[0].set_yticklabels(
            np.take(
                gene.ambler_numbering, (fig.axes[0].get_yticks() - 0.5).astype("int64")
            )
        )
        for ax in fig.axes[:-1]:
            data = ax.collections[0].get_array().data.reshape(rows, cols)
            # * adjust jupyter widget interactive hover values
            def format_coord(x, y):
                x = np.floor(x).astype("int")
                y = np.floor(y).astype("int")
                residue = df_wt.columns[x]
                pos = np.take(gene.ambler_numbering, y)
                value = data[y, x].round(4)
                return f"position: {pos}, residue: {residue}, value: {value}"

            ax.format_coord = format_coord
    elif orientation == "horizontal":
        fig.axes[0].set_xticklabels(
            np.take(
                gene.ambler_numbering, (fig.axes[0].get_xticks() - 0.5).astype("int64")
            )
        )
        for ax in fig.axes[:-1]:
            data = ax.collections[0].get_array().data.reshape(rows, cols)

            # * adjust jupyter widget interactive hover values
            def format_coord(x, y):
                x = np.floor(x).astype("int")
                y = np.floor(y).astype("int")
                residue = df_wt.columns[y]
                pos = np.take(gene.ambler_numbering, x)
                value = data[y, x].round(4)
                return f"position: {pos}, residue: {residue}, value: {value}"

            ax.format_coord = format_coord


def histogram_fitness_wrapper(
    sample: str, fitness_dict: dict, bins: list, ax: matplotlib.axes = None
) -> None:
    """
    Styler for individual histogram plotting fitness values. Gray bars show
    missense mutation values, green bars show synonymous mutation values, red
    bars show stop mutations values.

    Parameters
    ----------
    sample : str
        Sample to plot
    fitness_dict : dict
        Fitness DataFrames for all samples
    bins : list
        List of bin values
    ax : matplotlib.axes, optional
        AxesSubplot to plot on, by default None

    Returns
    -------
    None
    """
    if ax is None:
        ax = plt.gca()
    df_fitness = fitness_dict[sample]
    # selecting missense mutantions
    values_missense_filtered = df_fitness.drop(["*", "∅"], axis=1).values.flatten()
    # synonymous mutants
    values_syn_filtered = df_fitness["∅"].values.flatten()
    # stop mutations
    values_stop_filtered = df_fitness["*"].values.flatten()

    sns.histplot(
        values_missense_filtered,
        bins=bins,
        ax=ax,
        color="gray",
        label="missense mutations",
    )
    sns.histplot(
        values_syn_filtered,
        bins=bins,
        ax=ax,
        color="palegreen",
        alpha=0.6,
        label="synonymous mutations",
    )
    sns.histplot(
        values_stop_filtered,
        bins=bins,
        ax=ax,
        color="lightcoral",
        alpha=0.6,
        label="stop mutations",
    )

    ax.set_title(sample, fontweight="bold")
    ax.set_xlabel("distribution of fitness effects")
    ax.set_ylabel("counts", weight="bold")


def histogram_fitness_draw(
    counts_dict: dict, fitness_dict: dict, gene: Gene, read_threshold: int = 1
) -> matplotlib.figure:
    """
    Draw a histogram figure for fitness values of a dataset

    Parameters
    ----------
    counts_dict : dict
        DataFrames of count values for all samples
    fitness_dict : dict
        DataFrames of count values for all samples
    gene : Gene
        Object for locating wild-type residues
    read_threshold : int, optional
        Minimum number of reads for fitness value to be considered valid, by default 1

    Returns
    -------
    fig_dfe_all : matplotlib.figure
    """
    samples = list(sorted(fitness_dict))
    num_subplots = len(samples)
    num_rows = num_columns = int(np.round(np.sqrt(num_subplots)))
    if num_subplots / num_rows > num_rows:
        num_columns = num_rows + 1

    fitness_dict_filter = {
        sample: filter_fitness_read_noise(
            sample, counts_dict, fitness_dict, gene, read_threshold=read_threshold
        )
        for sample in samples
    }
    values_fitness_all = np.concatenate(
        [fitness_dict_filter[sample] for sample in samples]
    )
    bins = np.linspace(np.nanmin(values_fitness_all), np.nanmax(values_fitness_all), 51)
    with sns.axes_style("whitegrid"):
        fig_dfe_all, axes = plt.subplots(
            num_rows,
            num_columns,
            figsize=(10, 8),
            sharex=True,
            sharey=True,
            layout="constrained",
        )
        for i, sample in enumerate(samples):
            ax = axes.flat[i]
            histogram_fitness_wrapper(sample, fitness_dict_filter, bins, ax=ax)
        fig_dfe_all.get_layout_engine().set(hspace=0.1)
    return fig_dfe_all


def gaussian_drug(
    drug: str,
    counts_dict: dict,
    fitness_dict: dict,
    gene: Gene,
    read_threshold: int = 20,
    sigma_cutoff: int = 4,
    ax: matplotlib.axes = None,
    xlim: tuple[float, float] = (-2.5, 2.5),
    ylim: tuple[float, float] = (-2.5, 2.5),
) -> matplotlib.axes:
    x, y = get_pairs(drug, fitness_dict)
    df_x = filter_fitness_read_noise(
        x, counts_dict, fitness_dict, gene, read_threshold=read_threshold
    )
    df_y = filter_fitness_read_noise(
        y, counts_dict, fitness_dict, gene, read_threshold=read_threshold
    )

    sign_sensitive, sign_resistant, ellipses_all = gaussian_significance(
        df_x,
        df_y,
        sigma_cutoff=sigma_cutoff,
    )
    if ax is None:
        ax = plt.gca()

    # * draw the ellipses for each sigma cutoff
    for _, ellipse_sigma in ellipses_all.items():
        center, width, height, angle = ellipse_sigma
        ax.add_patch(
            Ellipse(
                center,
                width,
                height,
                angle=angle,
                ec="k",
                lw=0.667,
                fill=None,
                zorder=10,
            )
        )

    # * construct numpy matrix of all fitness values for plotting
    X = np.column_stack((df_x.values.flatten(), df_y.values.flatten()))
    # filter NaN in pairs
    X = X[np.isfinite(X).all(axis=1)]

    # * scatterplots
    # all mutations
    sns.scatterplot(
        x=X[:, 0],
        y=X[:, 1],
        zorder=-1,
        ax=ax,
        plotnonfinite=False,
        color="gray",
        lw=2,
        s=10,
    )
    # synonymous mutations
    sns.scatterplot(
        x=df_x["∅"],
        y=df_y["∅"],
        ax=ax,
        plotnonfinite=False,
        color="yellowgreen",
        lw=0.5,
        s=10,
    )
    # resistant mutations
    sns.scatterplot(
        x=df_x[sign_resistant].values.flatten(),
        y=df_y[sign_resistant].values.flatten(),
        ax=ax,
        plotnonfinite=False,
        color="lightcoral",
        lw=0.5,
        s=10,
    )
    # sensitive mutations
    sns.scatterplot(
        x=df_x[sign_sensitive].values.flatten(),
        y=df_y[sign_sensitive].values.flatten(),
        ax=ax,
        plotnonfinite=False,
        color="dodgerblue",
        lw=0.5,
        s=10,
    )

    # * axis lines and limits
    # diagonal
    ax.plot([-4, 4], [-4, 4], ":", color="gray", alpha=0.5, zorder=0)
    # x-axis
    ax.plot([0, 0], [-4, 4], "-", color="gray", alpha=0.5, lw=1, zorder=0)
    # y y-axis
    ax.plot([-4, 4], [0, 0], "-", color="gray", alpha=0.5, lw=1, zorder=0)
    ax.set(xlim=xlim, ylim=ylim, anchor="NW", aspect="equal")
    ax.set_xlabel(x, fontweight="bold")
    ax.set_ylabel(y, fontweight="bold")

    return ax


def gaussian_replica_pair_draw(
    counts_dict: dict,
    fitness_dict: dict,
    gene: Gene,
    read_threshold: int = 20,
    sigma_cutoff: int = 4,
    xlim: tuple[float, float] = (-2.5, 2.5),
    ylim: tuple[float, float] = (-2.5, 2.5),
) -> matplotlib.figure:
    """
    Draws the full figure of gaussian significance scatterplots for all drugs
    in experiment. All treated-untreated pairs must be present in the
    dictionary.

    Parameters
    ----------
    counts_dict : dict
        Reference with counts dataframes for all samples
    fitness_dict : dict
        Reference with fitness dataframes for all samples
    gene : Gene
        Gene object for locating wild-type residues
    read_threshold : int, optional
        Minimum number of reads required to be included, by default 20
    sigma_cutoff : int, optional
        How many sigmas away from the synonymous mutation values to use as the
        cutoff for significance, by default 4
    xlim : tuple[float, float], optional
        X-axis limits of figure, by default (-2.5, 2.5)
    ylim : tuple[float, float], optional
        Y-axis limits of figure, by default (-2.5, 2.5)

    Returns
    -------
    matplotlib.figure
    """
    # * determine shape of subplots
    drugs_all = sorted(set(x.rstrip("1234567890") for x in fitness_dict))
    num_plots = len(drugs_all)
    rows = cols = np.sqrt(num_plots)
    if not rows.is_integer():
        rows, cols = np.floor(rows), np.ceil(cols)
        if num_plots > rows * cols:
            rows += 1
    rows = int(rows)
    cols = int(cols)

    # * begin drawing
    fig, axs = plt.subplots(rows, cols, figsize=(10, 10), layout="compressed", dpi=300)
    for i, drug in enumerate(sorted(drugs_all)):
        ax = axs.flat[i]
        gaussian_drug(
            drug,
            counts_dict,
            fitness_dict,
            gene,
            read_threshold=read_threshold,
            sigma_cutoff=sigma_cutoff,
            ax=ax,
            xlim=xlim,
            ylim=ylim,
        )
    while len(fig.axes) > num_plots:
        fig.axes[-1].remove()
    fig.get_layout_engine().set(hspace=0.1, wspace=0.1)
    fig.suptitle(
        f"Significant mutations\nmin. reads = {read_threshold}, sigma cutoff = {sigma_cutoff}",
        fontweight="heavy",
        fontsize="x-large",
    )
    return fig


def shish_kabob_drug(
    drug: str,
    counts_dict: dict,
    fitness_dict: dict,
    gene: Gene,
    read_threshold: int = 20,
    sigma_cutoff: int = 4,
    ax: matplotlib.axes = None,
    orientation: str = "horizontal",
    vmin: float = -1.5,
    vmax: float = 1.5,
    cbar: bool = False,
) -> matplotlib.axes:
    """
    drug : str
        Name of drug to plot
    counts_dict : dict
        Reference with counts dataframes for all samples
    fitness_dict : dict
        Reference with fitness dataframes for all samples
    gene : Gene
        Gene object for locating wild-type residues
    read_threshold : int, optional
        Minimum number of reads required to be included, by default 20
    sigma_cutoff : int, optional
        How many sigmas away from the synonymous mutation values to use as the
        cutoff for significance, by default 4
    ax : matplotlib.axes, optional
        Axes to draw the plot on, by default None
    orientation : str, optional
        Whether to draw plot vertically or horizontally, by default "horizontal"
    vmin : float, optional
        For fitness data, vmin parameter passed to sns.heatmap, by default -1.5
    vmax : float, optional
        For fitness data, vmax parameter passed to sns.heatmap, by default 1.5
    cbar : bool, optional
        Whether to draw colorbar or not, by default False

    Returns
    -------
    ax : matplotlib.axes
    """
    replica_one, replica_two = get_pairs(drug, fitness_dict)
    df1 = filter_fitness_read_noise(
        replica_one, counts_dict, fitness_dict, gene, read_threshold=read_threshold
    )
    df2 = filter_fitness_read_noise(
        replica_two, counts_dict, fitness_dict, gene, read_threshold=read_threshold
    )

    sign_sensitive, sign_resistant, _ = gaussian_significance(
        df1,
        df2,
        sigma_cutoff=sigma_cutoff,
    )

    if ax is None:
        ax = plt.gca()
        # * get residue positions with significant mutations
    sign_positions = (
        sign_sensitive.drop("*", axis=1) | sign_resistant.drop("*", axis=1)
    ).sum(axis=1) > 0
    sign_positions = sign_positions[sign_positions].index
    # * find fitness value of greatest magnitude between pair
    df = df1[df1.abs().ge(df2.abs())]
    df.update(df2[df2.abs().ge(df1.abs())])
    # * select only mutations with significant fitness values
    df_masked = df.where(sign_resistant | sign_sensitive)
    df_masked = df_masked.drop("∅", axis=1)

    with sns.axes_style("white"):
        if orientation == "vertical":
            df_masked_plot = df_masked.loc[sign_positions]

            sns.heatmap(
                df_masked_plot,
                cmap="coolwarm",
                vmin=vmin,
                vmax=vmax,
                cbar=cbar,
                square=True,
                ax=ax,
            )
            ax.yaxis.grid("on")
            ax.set_yticks(
                np.arange(len(sign_positions)) + 0.5,
                np.array(sign_positions),
                rotation=0,
                ha="center",
                fontsize="xx-small",
            )
            ax.set_xticks([])
            # * add wild-type notations
            # get reference residues
            ref_aas = np.take(gene.cds_translation, sign_positions)
            # iterate over amino acid options (y-axis)
            for y, residue in enumerate(ref_aas):
                # determine x position for text box
                x = df_masked_plot.columns.get_loc(residue)
                ax.add_patch(
                    Rectangle((x, y), 1, 1, ec="black", fc="white", fill=True, lw=0.2)
                )
                ax.text(
                    x + 0.5,
                    y + 0.5,
                    residue,
                    fontsize="x-small",
                    ha="center",
                    va="center",
                )
            # * annotate fitness boxes
            # iterate over the x-axis (positions)
            for x, aa in enumerate(df_masked_plot.columns):
                # the significant positions of each amino acid mutation
                # determinates y-coord for text box
                pos_indices = np.argwhere(df_masked_plot[aa].notnull().values)
                for y in pos_indices:
                    ax.text(
                        x + 0.5,
                        y + 0.5,
                        aa,
                        fontsize="x-small",
                        ha="center",
                        va="center",
                        color="white",
                    )
            ax.set_title(drug, fontweight="heavy")
            ax.set_anchor("N")

        elif orientation == "horizontal":
            df_masked = df_masked.T
            df_masked_plot = df_masked[sign_positions]

            sns.heatmap(
                df_masked_plot,
                cmap="coolwarm",
                vmin=vmin,
                vmax=vmax,
                cbar=cbar,
                square=True,
                ax=ax,
            )
            ax.xaxis.grid("on")
            ax.set_xticks(
                np.arange(len(sign_positions)) + 0.5,
                np.array(sign_positions),
                rotation=90,
                ha="center",
                fontsize="xx-small",
            )
            ax.set_yticks([])
            # * annotate fitness boxes
            # get reference residues
            ref_aas = np.take(gene.cds_translation, sign_positions)
            # iterate in the x-direction (significant positions)
            for x, residue in enumerate(ref_aas):
                # determine y-coord for text box
                y = df_masked.index.get_loc(residue)
                ax.add_patch(
                    Rectangle(
                        (x, y),
                        1,
                        1,
                        ec="black",
                        fc="white",
                        fill=True,
                        lw=0.2,
                        clip_on=False,
                    )
                )
                ax.text(
                    x + 0.5,
                    y + 0.5,
                    residue,
                    fontsize="x-small",
                    ha="center",
                    va="center",
                )
            for x, pos in enumerate(sign_positions):
                aa_indices = np.argwhere(df_masked_plot[pos].notnull().values)
                for y in aa_indices:
                    aa = df_masked_plot.index[y].values[0]
                    ax.text(
                        x + 0.5,
                        y + 0.5,
                        aa,
                        fontsize="x-small",
                        ha="center",
                        va="center",
                        color="white",
                    )
            ax.set_ylabel(drug, fontweight="heavy")
            ax.set_anchor("W")
        return ax


def shish_kabob_draw(
    counts_dict: dict,
    fitness_dict: dict,
    gene: Gene,
    read_threshold: int = 20,
    sigma_cutoff: int = 4,
    orientation: str = "horizontal",
    vmin: float = -1.5,
    vmax: float = 1.5,
    xlim: tuple[float, float] = (-2.5, 2.5),
    ylim: tuple[float, float] = (-2.5, 2.5),
) -> matplotlib.axes:
    """
    Draw shish kabob plots and corresponding gaussian scatter plots for all
    samples in dataset

    Parameters
    ----------
    counts_dict : dict
        Reference with counts dataframes for all samples
    fitness_dict : dict
        Reference with fitness dataframes for all samples
    gene : Gene
        Gene object for locating wild-type residues
    read_threshold : int, optional
        Minimum number of reads required to be included, by default 20
    sigma_cutoff : int, optional
        How many sigmas away from the synonymous mutation values to use as the
        cutoff for significance, by default 4
    orientation : str, optional
        Whether to draw plot vertically or horizontally, by default "horizontal"
    vmin : float, optional
        For fitness data, vmin parameter passed to sns.heatmap, by default -1.5
    vmax : float, optional
        For fitness data, vmax parameter passed to sns.heatmap, by default 1.5
    xlim : tuple[float, float], optional
        X-axis limits of gaussian figure, by default (-2.5, 2.5)
    ylim : tuple[float, float], optional
        Y-axis limits of gaussian figure, by default (-2.5, 2.5)
    """
    # * determine shape of subplots
    drugs_all = sorted(set(x.rstrip("1234567890") for x in fitness_dict))
    gridspec_dict = {"wspace": 0, "hspace": 0}
    if orientation == "horizontal":
        num_rows, num_cols = len(drugs_all), 2
        gridspec_dict.update({"width_ratios": [2.5, 1]})
        figsize = (7, 17)
    elif orientation == "vertical":
        num_rows, num_cols = 2, len(drugs_all)
        gridspec_dict.update({"height_ratios": [2.5, 1]})
        figsize = (17, 7)

    with sns.axes_style("white"):
        fig, axs = plt.subplots(
            num_rows,
            num_cols,
            figsize=figsize,
            dpi=300,
            layout="constrained",
            gridspec_kw=gridspec_dict,
        )
        fig.suptitle(
            f"Significant mutations\nmin. read = {read_threshold}, sigma cutoff = {sigma_cutoff}",
            fontsize="large",
            fontweight="heavy",
        )
        for i, drug in enumerate(drugs_all):
            # * determine subplots for shish kabob and gaussians
            if orientation == "horizontal":
                ax_shish = axs[i, 0]
                ax_gauss = axs[i, 1]
            elif orientation == "vertical":
                ax_shish = axs[0, i]
                ax_gauss = axs[1, i]
            ax_gauss.set_xlabel(f"{drug}1", size="x-small")
            ax_gauss.set_ylabel(f"{drug}2", size="x-small")
            ax_gauss.tick_params(labelsize="xx-small")
            ax_gauss.set_anchor("W")

            gaussian_drug(
                drug,
                counts_dict,
                fitness_dict,
                gene,
                read_threshold=read_threshold,
                sigma_cutoff=sigma_cutoff,
                ax=ax_gauss,
                xlim=xlim,
                ylim=ylim,
            )

            shish_kabob_drug(
                drug,
                counts_dict,
                fitness_dict,
                gene,
                read_threshold=read_threshold,
                sigma_cutoff=sigma_cutoff,
                ax=ax_shish,
                orientation=orientation,
                vmin=vmin,
                vmax=vmax,
            )

    return fig


def drug_pair(
    drug1: str,
    drug2: str,
    counts_dict: dict,
    fitness_dict: dict,
    gene: Gene,
    ax: matplotlib.axes = None,
    read_threshold: int = 20,
    sigma_cutoff: int = 4,
    xlim: tuple[float, float] = (-2.5, 2.5),
    ylim: tuple[float, float] = (-2.5, 2.5),
) -> None:
    """
    Find common significant resistance/sensitivity mutations between two different drugs

    Parameters
    ----------
    drug1 : str
        First drug
    drug2 : str
        Second drug
    counts_dict : dict
        Reference with counts dataframes for all samples
    fitness_dict : dict
        Reference with fitness dataframes for all samples
    gene : Gene
        Gene object for locating wild-type residues
    ax : matplotlib.axes, optional
        Axes to draw the plot on, by default
    read_threshold : int, optional
        Minimum number of reads required to be included, by default 20
    sigma_cutoff : int, optional
        How many sigmas away from the synonymous mutation values to use as the
        cutoff for significance, by default 4
    xlim : tuple[float, float], optional
        X-axis limits of figure, by default (-2.5, 2.5)
    ylim : tuple[float, float], optional
        y-axis limits of figure, by default (-2.5, 2.5)
    """
    if ax is None:
        ax = plt.gca()
    # * get cells of significant mutations
    # drug 1
    drug1_x, drug1_y = get_pairs(drug1, fitness_dict)
    df1_x = filter_fitness_read_noise(
        drug1_x, counts_dict, fitness_dict, gene, read_threshold=read_threshold
    )
    df1_y = filter_fitness_read_noise(
        drug1_y, counts_dict, fitness_dict, gene, read_threshold=read_threshold
    )
    df_sign_sensitive1, df_sign_resistant1, _ = gaussian_significance(
        df1_x, df1_y, sigma_cutoff=sigma_cutoff
    )
    # drug 2
    drug2_x, drug2_y = get_pairs(drug2, fitness_dict)
    df2_x = filter_fitness_read_noise(
        drug2_x, counts_dict, fitness_dict, gene, read_threshold=read_threshold
    )
    df2_y = filter_fitness_read_noise(
        drug2_y, counts_dict, fitness_dict, gene, read_threshold=read_threshold
    )
    df_sign_sensitive2, df_sign_resistant2, _ = gaussian_significance(
        df2_x, df2_y, sigma_cutoff=sigma_cutoff
    )
    # * find mean of fitness values between replicates
    df1_xy = pd.concat([df1_x, df1_y]).groupby(level=0, axis=0).agg(np.mean)
    df2_xy = pd.concat([df2_x, df2_y]).groupby(level=0, axis=0).agg(np.mean)
    # * build numpy matrix of all points for plotting
    X = np.column_stack((df1_xy.values.flatten(), df2_xy.values.flatten()))
    X = X[np.isfinite(X).all(axis=1)]

    # * scatterplots
    # all mutations
    sns.scatterplot(
        x=X[:, 0],
        y=X[:, 1],
        zorder=-1,
        ax=ax,
        plotnonfinite=False,
        color="gray",
        lw=2,
        s=10,
    )
    # * sensitive mutations
    # drug 1 sensitive mutations
    sns.scatterplot(
        x=df1_xy[df_sign_sensitive1].values.flatten(),
        y=df2_xy[df_sign_sensitive1].values.flatten(),
        ax=ax,
        plotnonfinite=False,
        color="dodgerblue",
        lw=2,
        s=10,
    )
    # drug 2 sensitive mutations
    sns.scatterplot(
        x=df1_xy[df_sign_sensitive2].values.flatten(),
        y=df2_xy[df_sign_sensitive2].values.flatten(),
        ax=ax,
        plotnonfinite=False,
        color="dodgerblue",
        lw=2,
        s=10,
    )
    # drug1-drug2 shared sensitive mutations
    shared_sensitive_1 = df1_xy.where(df_sign_sensitive1 & df_sign_sensitive2)
    shared_sensitive_2 = df2_xy.where(df_sign_sensitive1 & df_sign_sensitive2)
    sns.scatterplot(
        x=shared_sensitive_1.values.flatten(),
        y=shared_sensitive_2.values.flatten(),
        ax=ax,
        plotnonfinite=False,
        color="mediumblue",
        lw=2,
        s=10,
        marker="D",
    )
    # * resistance mutations
    # drug 1 resistance mutations
    sns.scatterplot(
        x=df1_xy[df_sign_resistant1].values.flatten(),
        y=df2_xy[df_sign_resistant1].values.flatten(),
        ax=ax,
        plotnonfinite=False,
        color="lightcoral",
        lw=2,
        s=10,
    )
    # drug 2 resistance mutations
    sns.scatterplot(
        x=df1_xy[df_sign_resistant2].values.flatten(),
        y=df2_xy[df_sign_resistant2].values.flatten(),
        ax=ax,
        plotnonfinite=False,
        color="lightcoral",
        lw=2,
        s=10,
    )
    # drug1-drug2 shared resistance mutations
    shared_resistant_1 = df1_xy.where(df_sign_resistant1 & df_sign_resistant2)
    shared_resistant_2 = df2_xy.where(df_sign_resistant1 & df_sign_resistant2)
    sns.scatterplot(
        x=shared_resistant_1.values.flatten(),
        y=shared_resistant_2.values.flatten(),
        ax=ax,
        plotnonfinite=False,
        color="firebrick",
        lw=2,
        s=10,
        marker="D",
    )

    ax.plot([-4, 4], [-4, 4], ":", color="gray", alpha=0.5, zorder=0)
    ax.plot([0, 0], [-4, 4], "-", color="gray", alpha=0.5, lw=1, zorder=0)
    ax.plot([-4, 4], [0, 0], "-", color="gray", alpha=0.5, lw=1, zorder=0)
    ax.set(xlim=xlim, ylim=ylim)
    ax.tick_params(left=False, bottom=False, labelsize="xx-small")
    ax.set_anchor("NW")
    ax.set_aspect("equal")
    return ax


def drug_pairs_draw(
    counts_dict: dict,
    fitness_dict: dict,
    gene: Gene,
    read_threshold: int = 20,
    sigma_cutoff: int = 4,
):
    drugs_all = sorted(set(x.rstrip("1234567890") for x in fitness_dict))
    rows = cols = len(drugs_all) - 1
    fig, axs = plt.subplots(
        rows,
        cols,
        figsize=(15, 15),
        layout="compressed",
        sharex="col",
        sharey="row",
        gridspec_kw={"hspace": 0, "wspace": 0},
        dpi=300,
    )
    for ax_row, drug_y in enumerate(drugs_all):
        for ax_col, drug_x in enumerate(drugs_all):
            if ax_row > ax_col:
                ax = axs[ax_row - 1, ax_col]
                drug_pair(
                    drug_x,
                    drug_y,
                    counts_dict=counts_dict,
                    fitness_dict=fitness_dict,
                    gene=gene,
                    ax=ax,
                    read_threshold=read_threshold,
                    sigma_cutoff=sigma_cutoff,
                )
                if ax_col == 0:
                    ax.set_ylabel(drug_y)
                if ax_row == len(drugs_all) - 1:
                    ax.set_xlabel(drug_x)
            elif ax_row > 0 and (ax_col < len(drugs_all) - 1):
                ax = axs[ax_row - 1, ax_col]
                ax.set_in_layout(False)
                ax.remove()
    fig.suptitle(
        f"min. reads: {read_threshold}\nsigma cutoff: {sigma_cutoff}",
        x=0.7,
        y=0.7,
        fontsize="xx-large",
        fontweight="heavy",
    )
    return fig
