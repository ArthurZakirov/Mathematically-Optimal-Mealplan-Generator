import pandas as pd
from langchain.pydantic_v1 import BaseModel, Field, create_model
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain_openai.output_parsers import JsonOutputKeyToolsParser

from src.my_langchain.chain import build_chain_from_config


def processed_df_column_with_llm(chain, column, delimiter="\n-"):
    """
    Append a column to the DataFrame containing the output of the LLM chain.
    LLM chain takes all the values in the "Search Result Name" column as input in a single string.
    Therefore, the LLM is aware of all the rows in the dataframe.
    """

    user_input = delimiter.join(column)

    output = chain.invoke(user_input)["output"]
    llm_df = pd.DataFrame(output["items"])
    return llm_df


def pandas_llm_merge(df_1, df_2, left_on, right_on, chain_config, chunk_size=20):
    chain = build_chain_from_config(chain_config)

    num_chunks = (len(df_1) + chunk_size - 1) // chunk_size
    final_merged_dfs = []

    names_2 = "\n".join(df_2.index.astype(str) + ": " + df_2[right_on])

    index_1 = chain_config.response_schema.fields[0].name
    index_2 = chain_config.response_schema.fields[1].name

    for i in range(num_chunks):
        chunk = df_1.iloc[i * chunk_size : (i + 1) * chunk_size]
        names_1 = "\n".join(chunk.index.astype(str) + ": " + chunk[left_on])

        raw_outputs = chain.invoke({"NAMES_1": names_1, "NAMES_2": names_2})
        output = raw_outputs[0]["args"]["items"]

        similarity_df = pd.DataFrame(output)

        if isinstance(left_on, tuple):
            similarity_df.columns = pd.MultiIndex.from_tuples(
                [("Similarity", col) for col in similarity_df.columns]
            )

            merged_df = pd.merge(
                similarity_df,
                chunk,
                how="left",
                left_on=("Similarity", index_1),
                right_index=True,
            )
            final_df = pd.merge(
                merged_df,
                df_2,
                how="left",
                left_on=("Similarity", index_2),
                right_index=True,
            )

        else:
            merged_df = pd.merge(
                similarity_df, chunk, how="left", left_on=index_1, right_index=True
            )

            final_df = pd.merge(
                merged_df, df_2, how="left", left_on=index_2, right_index=True
            )

            final_df.drop(
                columns=[
                    col
                    for col in final_df.columns
                    if (index_1 in col or index_2 in col)
                ],
                inplace=True,
            )

        final_merged_dfs.append(final_df)

    # Concatenate all processed chunks into one DataFrame
    final_merged_df = pd.concat(final_merged_dfs, ignore_index=True)
    return final_merged_df
