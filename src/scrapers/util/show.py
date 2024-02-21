from typing import Optional


class Show:
    def __init__(self, url: str, name: str, status: str, imdbid: Optional[str] = None):
        """
        _summary_

        Args:
            url (str): _description_
            name (str): _description_
            status (str): _description_
            imdbid (str | None, optional): _description_. Defaults to None.
        """
        self.url = url
        self.name = name
        self.status = status
        self.imdbid = imdbid

    def __repr__(self):
        return f"Show(url='{self.url}', name='{self.name}', status='{self.status}', imdbid='{self.imdbid}')"
