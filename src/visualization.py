#!/usr/bin/env python
import re

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from Bio.Data import IUPACData
from matplotlib.offsetbox import AnchoredText
from matplotlib.patches import Rectangle
from scipy.stats import norm
from sequencing_data import filter_fitness_read_noise


def heatmap_table(gene):
    df = pd.DataFrame(
        False,
        index=np.arange(len(gene.cds_translation)),
        columns=list(IUPACData.protein_letters + "*∅"),
    )
    return df


# //* should do something about the numbering flexibility here
def heatmap_masks(gene):
    df_wt = heatmap_table(gene)
    for position, residue in enumerate(gene.cds_translation):
        df_wt.loc[position, residue] = True
    return df_wt

def respine(ax):
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


def histogram_mutation_counts(SequencingData):
    counts = SequencingData.counts
    num_plots = len(counts)
    height = num_plots * 1.8

    fig, axes = plt.subplots(
        nrows=num_plots, figsize=(5, height), constrained_layout=True, sharey=True
    )
    fig.suptitle("Distribution of counts for all amino acids")

    for i, sample in enumerate(counts):
        # * // these indices are specific to the mature TEM-1 protein
        # * // would need to be changed if you used a different gene
        counts_values = counts[sample].loc[23:285, :"Y"]
        num_missing = counts_values.lt(1).sum().sum() - counts_values.shape[0]
        with np.errstate(divide="ignore"):
            log_values = counts_values.where(
                counts_values.lt(1), np.log10(counts_values)
            )
        log_values = log_values.where(log_values != 0.01, np.nan).values.flatten()
        # * // total number of mutants specific to TEM-1 library
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


def heatmap_missing_mutations(df, ax=None, cbar_ax=None, orientation="vertical"):
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

    # set title

    return ax


def heatmap_wrapper(
    df: pd.DataFrame,
    name: str,
    dataset: str,
    gene,
    ax=None,
    cbar=False,
    cbar_ax=None,
    vmin=-2,
    vmax=2,
    fitness_cmap="vlag",
    orientation="horizontal",
):
    """
    Function wrapper for preferred heatmap aesthetic settings

    Parameters
    ----------
    df : pandas.DataFrame
        Matrix to be plotted
    name : str
        Sample name for axes labeling
    dataset : str
        Type of data ("counts" or "fitness")
    gene : str
        Gene object to provide residue numbering
    ax : matplotlib.Axes, optional
        Axes on which to draw the data, by default None
    cbar : bool, optional
        Whether to draw a colorbar or not, by default False
    cbar_ax : matplotlib.Axes, optional
        Axes on which to draw the colorbar, by default None
    vmin : int, optional
        For fitness data, vmin parameter passed to sns.heatmap, by default -2
    vmax : int, optional
        For fitness data, vmax parameter passed to sns.heatmap, by default 2
    fitness_cmap : str, optional
        Colormap to use for fitness heatmap, by default "vlag"
    orientation : str, optional
        Whether to draw heatmaps vertically or horizontally, by default "horizontal"

    Returns
    -------
    h : matplotlib.Axes
        Axes object with the heatmap
    """
    if dataset == "counts":
        with np.errstate(divide="ignore"):
            df = df.where(df.lt(1), np.log10(df))
            cmap = "Blues"
            vmin = None
            vmax = None
    elif dataset == "fitness":
        cmap = "vlag"

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
    h.set_facecolor("black")
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
    gene,
    read_threshold=1,
    vmin=-2,
    vmax=2,
    fitness_cmap="vlag",
    orientation="horizontal",
):
    """
    Draw a heatmap of a dataset
    # TODO: Consider re-adding figure to make a missing chart, but perhaps not really necessary
    # TODO: Add read_threshold parameter or change fitness attribute to be filtered

    Parameters
    ----------
    df_dict : dict
        Sample names with datatables
    dataset : str
        Whether to draw a heatmap for raw (log-transformed) counts or fitness data
    gene : Gene
        Gene object that provides residue numbering
    vmin : int, optional
        For fitness data, vmin parameter passed to sns.heatmap, by default -2
    vmax : int, optional
        For fitness data, vmax parameter passed to sns.heatmap, by default 2
    fitness_cmap : str, optional
        Colormap to use for fitness heatmap, by default "vlag"
    orientation : str, optional
        Whether to draw heatmaps vertically or horizontally, by default "horizontal"

    Returns
    -------
    fig
        matplotlib.Figure
    """

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
        df_dict = fitness_dict_filter = {
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
        # * function-provided styling for heatmap
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
        height = 0
        for ax in fig.axes:
            ax.tick_params(labelleft=True)
            height += (
                ax.get_tightbbox().transformed(fig.dpi_scale_trans.inverted()).height
            )
        fig.axes[0].tick_params(labeltop=True)
        fig.set_figheight(height + 1)
        pad = fig.get_layout_engine().get()["hspace"] / 2
    elif orientation == "vertical":
        for ax in fig.axes:
            ax.tick_params(labelbottom=True)
        fig.axes[0].tick_params(labelleft=True)
        fig.set_figheight(fig.get_tightbbox().height)
        pad = fig.get_layout_engine().get()["wspace"] / 2
    cbar = fig.colorbar(
        axs[0].collections[0],
        ax=fig.axes,
        shrink=0.2,
        fraction=0.1,
        # pad=0.05,
        pad=pad,
        anchor="NW",
        location=cbar_location,
        use_gridspec=True,
    )
    cbar.ax.spines["outline"].set_lw(0.4)
    cbar.ax.tick_params(right=False, left=False, labelsize=4, length=0, pad=3)
    return fig


def relabel_axis(fig, gene, orientation="horizontal"):
    """
    Here we relabel the position-axis of the heatmap figure to use the Ambler numbering system.

    Parameters
    ----------
    fig : matplotlib.figure
        Parent figure of all the heatmap axes
    gene : plasmid_map.Gene
        Gene object that holds a numbering system attribute
    orientation : str, optional
        Whether the heatmaps are drawn horizontally or vertically, by default "horizontal"

    Returns
    -------
    None
    """

    df_wt = heatmap_masks(gene).loc[285]
    if orientation == "vertical":
        fig.axes[0].set_yticklabels(
            np.take(
                gene.ambler_numbering, (fig.axes[0].get_yticks() - 0.5).astype("int64")
            )
        )
        for ax in fig.axes[:-1]:
            data = ax.collections[0].get_array().data.reshape(287, 22)

            def format_coord(x, y):
                df_wt = heatmap_masks(gene)
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
            data = ax.collections[0].get_array().data.reshape(22, 287)

            def format_coord(x, y):
                x = np.floor(x).astype("int")
                y = np.floor(y).astype("int")
                residue = df_wt.columns[y]
                pos = np.take(gene.ambler_numbering, x)
                value = data[y, x].round(4)
                return f"position: {pos}, residue: {residue}, value: {value}"

            ax.format_coord = format_coord


def histogram_fitness_wrapper(sample, fitness_dict, bins, ax=None):
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


def histogram_fitness_draw(counts_dict, fitness_dict, gene, read_threshold=1):
    samples = [key for key in sorted(fitness_dict)]
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
