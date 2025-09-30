"""Completions Module for Mistral models
"""

import os
import json
import time
from mistralai import Mistral, SDKError
from dotenv import load_dotenv

load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")


class CL_Mistral_Completions:
    """
    Responsible for generating text completions, document summaries, and timeline descriptions
    using the Mistral API.

    Attributes:
        client (Mistral): Mistral API client instance.
        model (str): Name of the Mistral model to use.
        temperature (float): Sampling temperature for completions.
    """

    def __init__(self, model="mistral-small-latest", temperature=0.5):
        """
        Initialize the CL_Mistral_Completions client.

        :param model: Model name to use for completions (default: "mistral-small-latest")
        :param temperature: Sampling temperature (0.0-1.0) for creativity in responses
        """
        self.client = Mistral(api_key=MISTRAL_API_KEY)
        self.model = model
        self.temperature = temperature

    def generate_description(self, desc_title: str, list_summaries: list[str]) -> str:
        """
        Generate an overarching description for a timeline, based on summaries of multiple documents.

        :param desc_title: Title of the timeline
        :param list_summaries: List of document summaries that form the timeline

        :returns: Generated descriptive text summarizing the timeline
        :rtype: str
        """
        prompt = f"""
            Je krijgt de samenvattingen van meerdere documenten die samen de inhoud van de tijdlijn "{desc_title}" vormen.

            Schrijf een beschrijvende inleiding van maximaal 10 zinnen die de lezer uitlegt wat hij of zij in deze tijdlijn kan verwachten. 
            ...
            Samenvattingen:
            {chr(10).join(list_summaries)}
            """
        return self._generate_completion(prompt)

    def generate_doc_summary(self, doc: dict, tijdlijn_title: str) -> str:
        """
        Generate a summary for a single document.

        :param doc: Dictionary containing the document data, including 'content_text' (list of chunks)
        :param tijdlijn_title: Title of the timeline the document belongs to

        :returns: Generated summary text
        :rtype: str
        """
        chunks = doc["content_text"]

        if len(chunks) == 1:
            # One chunk → direct summary
            prompt = (
                f"""Vat onderstaand document samen in één alinea van maximaal 10 zinnen.
                Document: {chunks[0]['content']}"""
            )
            return self._generate_completion(prompt)
        else:
            # Multiple chunks → summarize per chunk and combine
            chunk_summaries = []
            for chunk in chunks:
                prompt = (
                    f"""Vat de onderstaande tekst samen in 3-6 bulletpoints.
                    Tekst:{chunk['content']}"""
                )
                summary = self._generate_completion(prompt)
                chunk_summaries.append(summary)

            combined_prompt = (
                f"""Geef een samenvatting van de totale inhoud van alle onderstaande bulletpoints van één alinea.
                Bulletpoints: {chr(10).join(chunk_summaries)}"""
            )
            return self._generate_completion(combined_prompt)

    def _generate_completion(self, prompt: str) -> str:
        """
        Generate a text completion for a given prompt using the Mistral API.

        :param prompt: The user prompt to send to the model
        :returns: Generated completion text
        
        :raises TypeError: If prompt is not a string
        :raises SDKError: If the Mistral API call fails
        """
        if not isinstance(prompt, str):
            raise TypeError(f"Expected prompt to be a string, but got: {type(prompt)}")

        try:
            response = self.client.chat.complete(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature
            )
        except SDKError as e:
            print("Error from SDK:", str(e))
            time.sleep(3)
            print("Retrying completion...")
            response = self.client.chat.complete(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature
            )

        return response.choices[0].message.content
