import os

from .data_model.study import Study
import compute
from .compute.predict import PredictorConfigManager, PredictorDataSetManager
import data_model
from .datapackage import make_study_datapackage, FLOTILLA_DOWNLOAD_DIR
import visualize

__version__ = '0.2.5dev'

# 18 cells, multiindex on the splicing data features, features already renamed
# in the matrices
_shalek2013 = 'https://raw.githubusercontent.com/YeoLab/shalek2013/master/' \
              'datapackage.json'

# 250 cells, ensembl and miso ids on index, need renaming, lots of celltypes
_test_data = 'https://raw.githubusercontent.com/YeoLab/flotilla_test_data/' \
             'master/datapackage.json'

def embark(study_name, load_species_data=True):
    """
    Begin your journey of data exploration.

    Parameters
    ----------
    data_package_url : str
        A URL to a datapackage.json file

    Returns
    -------
    study : flotilla.Study
        A biological study created from the data package specified
    """
    try:
        try:
            return Study.from_datapackage_file(study_name,
                                               load_species_data=load_species_data)
        except IOError:
            pass
        filename = os.path.abspath(os.path.expanduser(
            '{}/{}/datapackage.json'.format(FLOTILLA_DOWNLOAD_DIR,
                                            study_name)))
        return Study.from_datapackage_file(filename,
                                           load_species_data=load_species_data)
    except IOError:
        return Study.from_datapackage_url(study_name,
                                          load_species_data=load_species_data)
