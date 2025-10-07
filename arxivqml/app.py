"""
Streamlit web interface for browsing curated arXiv papers.
"""

import streamlit as st
import plotly.express as px
import pandas as pd
from datetime import datetime
from arxivqml import database
from arxivqml import config

# Page configuration
st.set_page_config(
    page_title="arXiv QML Paper Browser",
    page_icon="📚",
    layout="wide"
)

def format_date(date_obj):
    """Format datetime object to readable string."""
    if isinstance(date_obj, datetime):
        return date_obj.strftime("%Y-%m-%d")
    return str(date_obj)

def show_paper_browser(collection):
    """Paper browser tab - browse and filter papers."""
    # Get total count
    total_count = collection.count_documents({})
    st.sidebar.markdown(f"**Total papers in database:** {total_count}")

    # Sidebar filters
    st.sidebar.header("🔍 Filters")

    # Relevance score filter
    min_score = st.sidebar.slider(
        "Minimum Relevance Score",
        min_value=1,
        max_value=10,
        value=config.MIN_RELEVANCE_SCORE,
        help="Filter papers by minimum relevance score"
    )

    # Category filter
    all_categories = database.get_unique_categories(collection)
    selected_categories = st.sidebar.multiselect(
        "Primary Categories",
        options=all_categories,
        default=all_categories,
        help="Filter by arXiv primary category"
    )

    # Keyword filter
    all_keywords = database.get_unique_keywords(collection)
    selected_keywords = st.sidebar.multiselect(
        "Keywords",
        options=all_keywords,
        help="Filter by keywords (papers must contain ALL selected keywords)"
    )

    # Date filters
    st.sidebar.subheader("📅 Date Range")

    # Get date range from DB
    oldest_paper = collection.find_one(sort=[("published", 1)])
    newest_paper = collection.find_one(sort=[("published", -1)])

    if oldest_paper and newest_paper:
        min_date = oldest_paper["published"].date()
        max_date = newest_paper["published"].date()

        date_from = st.sidebar.date_input(
            "Published From",
            value=min_date,
            min_value=min_date,
            max_value=max_date
        )

        date_to = st.sidebar.date_input(
            "Published To",
            value=max_date,
            min_value=min_date,
            max_value=max_date
        )
    else:
        date_from = None
        date_to = None

    # Sorting options
    st.sidebar.header("📊 Sorting")
    sort_by = st.sidebar.selectbox(
        "Sort By",
        options=["relevance_score", "published", "updated"],
        format_func=lambda x: {
            "relevance_score": "Relevance Score",
            "published": "Published Date",
            "updated": "Updated Date"
        }[x]
    )

    sort_order_label = st.sidebar.radio(
        "Sort Order",
        options=["Descending", "Ascending"]
    )
    sort_order = -1 if sort_order_label == "Descending" else 1

    # Build MongoDB query
    query_filters = {"relevance_score": {"$gte": min_score}}

    if selected_categories:
        query_filters["primary_category"] = {"$in": selected_categories}

    if selected_keywords:
        query_filters["keywords"] = {"$all": selected_keywords}

    if date_from and date_to:
        query_filters["published"] = {
            "$gte": datetime.combine(date_from, datetime.min.time()),
            "$lte": datetime.combine(date_to, datetime.max.time())
        }

    # Query database
    papers = database.get_all_papers(
        collection,
        filters=query_filters,
        sort_by=sort_by,
        sort_order=sort_order
    )

    # Display results
    st.markdown(f"### 📄 Results: {len(papers)} papers")

    if not papers:
        st.info("No papers found matching the selected filters.")
        return

    # Display papers
    for i, paper in enumerate(papers, 1):
        with st.expander(f"**{i}. {paper['title']}** (Score: {paper.get('relevance_score', 'N/A')}/10)"):
            col1, col2 = st.columns([2, 1])

            with col1:
                st.markdown(f"**Authors:** {', '.join(paper['authors'][:3])}" +
                           (f" *et al.*" if len(paper['authors']) > 3 else ""))
                st.markdown(f"**Published:** {format_date(paper.get('published', 'N/A'))}")
                st.markdown(f"**Updated:** {format_date(paper.get('updated', 'N/A'))}")
                st.markdown(f"**Primary Category:** {paper.get('primary_category', 'N/A')}")
                st.markdown(f"**Categories:** {', '.join(paper.get('categories', []))}")

            with col2:
                st.markdown(f"**Relevance Score:** {paper.get('relevance_score', 'N/A')}/10")
                st.markdown(f"**Keywords:** {', '.join(paper.get('keywords', []))}")
                st.markdown(f"**[📄 View on arXiv]({paper.get('pdf_url', '#')})**")

            st.markdown("**Abstract:**")
            st.write(paper.get('summary', 'No abstract available'))

            if paper.get('score_justification'):
                st.markdown("**Score Justification:**")
                st.info(paper['score_justification'])

def show_keyword_manager(collection):
    """Keyword Manager tab - visualize and manage keyword mappings."""
    st.header("🔧 Keyword Manager")
    st.markdown("Visualize, merge, and organize keywords from your paper collection")

    # Load current mappings
    keyword_data = database.load_keyword_mappings()
    mappings = keyword_data.get("mappings", {})
    hierarchy = keyword_data.get("hierarchy", {})

    # Get keyword frequencies
    keyword_freq = database.get_keyword_frequencies(collection)

    if not keyword_freq:
        st.info("No keywords found in database.")
        return

    # Create tabs within Keyword Manager
    viz_tab, merge_tab, hierarchy_tab = st.tabs([
        "📊 Visualization",
        "🔄 Merge Keywords",
        "📂 Hierarchy"
    ])

    # Tab 1: Visualization
    with viz_tab:
        st.subheader("Keyword Frequency Visualization")

        # Create dataframe for plotting
        keyword_df = pd.DataFrame([
            {"keyword": kw, "count": count}
            for kw, count in keyword_freq.items()
        ]).sort_values("count", ascending=False)

        # Frequency threshold filter
        min_freq = st.slider(
            "Minimum frequency (papers)",
            min_value=1,
            max_value=max(keyword_freq.values()),
            value=1
        )

        filtered_df = keyword_df[keyword_df["count"] >= min_freq]

        st.markdown(f"**Showing {len(filtered_df)} keywords (≥{min_freq} papers)**")

        # Treemap visualization
        if len(filtered_df) > 0:
            fig = px.treemap(
                filtered_df,
                path=[px.Constant("All Keywords"), "keyword"],
                values="count",
                hover_data=["count"],
                title="Keyword Distribution (click to explore)"
            )
            fig.update_traces(textinfo="label+value")
            st.plotly_chart(fig, use_container_width=True)

            # Show top keywords table
            st.subheader("Top Keywords")
            st.dataframe(
                filtered_df.head(20),
                use_container_width=True,
                hide_index=True
            )

    # Tab 2: Merge Keywords
    with merge_tab:
        st.subheader("Merge Similar Keywords")
        st.markdown("Select multiple keywords to merge into a canonical form")

        col1, col2 = st.columns([2, 1])

        with col1:
            # Show all keywords with checkboxes
            all_keywords = sorted(keyword_freq.keys())
            selected_keywords = st.multiselect(
                "Select keywords to merge",
                options=all_keywords,
                help="Choose variants of the same concept to merge"
            )

        with col2:
            if selected_keywords:
                # Show affected papers count
                total_affected = sum(keyword_freq.get(kw, 0) for kw in selected_keywords)
                st.metric("Papers affected", total_affected)

        if selected_keywords:
            st.markdown("---")

            # Canonical form input
            canonical_form = st.text_input(
                "Canonical form (standardized keyword)",
                value=selected_keywords[0],
                help="This will be the normalized form"
            )

            # Preview section
            st.markdown("**Preview:**")
            st.write(f"Will merge: `{', '.join(selected_keywords)}` → `{canonical_form}`")

            # Apply button
            col_a, col_b = st.columns([1, 3])
            with col_a:
                if st.button("Apply Merge", type="primary"):
                    # Update mappings
                    if canonical_form not in mappings:
                        mappings[canonical_form] = []

                    # Add selected keywords to mapping
                    for kw in selected_keywords:
                        if kw not in mappings[canonical_form]:
                            mappings[canonical_form].append(kw)

                    try:
                        # Save mappings (atomic write with backup)
                        keyword_data["mappings"] = mappings
                        database.save_keyword_mappings(keyword_data)

                        # Apply to database
                        updated, errors = database.normalize_paper_keywords(collection, mappings)

                        if errors > 0:
                            st.warning(f"✅ Merged {len(selected_keywords)} keywords → '{canonical_form}' ({updated} papers updated, {errors} errors)")
                        else:
                            st.success(f"✅ Merged {len(selected_keywords)} keywords → '{canonical_form}' ({updated} papers updated)")
                        st.rerun()

                    except Exception as e:
                        st.error(f"❌ Merge failed: {e}")
                        st.info("Your keywords.json.bak file is safe. Check logs for details.")

            with col_b:
                st.caption("This will update the database and keywords.json file")

        # Show current mappings
        st.markdown("---")
        st.subheader("Current Keyword Mappings")

        if mappings:
            for canonical, variants in sorted(mappings.items()):
                with st.expander(f"**{canonical}** ({len(variants)} variants)"):
                    st.write(", ".join(variants))
        else:
            st.info("No keyword mappings defined yet")

    # Tab 3: Hierarchy
    with hierarchy_tab:
        st.subheader("Keyword Hierarchy")
        st.markdown("Organize keywords into categories (coming soon)")
        st.info("Drag-and-drop hierarchy editor will be added in future update")

        # Display current hierarchy as JSON for now
        if hierarchy:
            st.json(hierarchy)

def main():
    """Main app entry point."""
    st.title("📚 arXiv QML Research Assistant")

    # Connect to database
    collection = database.get_db_collection()
    if collection is None:
        st.error("❌ Failed to connect to MongoDB. Please check your configuration.")
        return

    # Create tabs
    tab1, tab2 = st.tabs(["📄 Paper Browser", "🔧 Keyword Manager"])

    with tab1:
        show_paper_browser(collection)

    with tab2:
        show_keyword_manager(collection)

if __name__ == "__main__":
    main()
