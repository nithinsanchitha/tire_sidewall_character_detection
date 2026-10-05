# Adding tire photos

Sample assets are separate from user uploads (`data/images/`, excluded from Git). No real tire photograph is bundled, and no supplied asset is claimed to have been captured by the project owner.

Candidate sources identified on Wikimedia Commons:
- [Sidewall.jpg](https://commons.wikimedia.org/wiki/File:Sidewall.jpg): marked CC BY-SA 3.0 in its listing. Verify current creator and licensing before use; retain attribution and license if redistributing.
- [TyreMarkings.jpg](https://commons.wikimedia.org/wiki/File:TyreMarkings.jpg): Kifoc, 23 February 2008; listed as a public-domain release. This is an annotated marking illustration, unsuitable as an unannotated real-image accuracy test.

The original asset/license pages could not be retrieved reliably in this environment, so neither asset has been copied. Prefer your own clear close-up photo or obtain a properly licensed original, then upload it through the interface. Do not commit private photos.

`python scripts/make_smoke_image.py` creates a project-authored synthetic text target under `data/`. It says **NOT A TIRE** and is only for OCR/API smoke testing. The included screenshots show that target and an intentional user correction to TOYO; they do not establish tire recognition performance.
