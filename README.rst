BA-POSGMCP
###########

This repository contains the implementation of the Bayes Adaptive Monte-Carlo Planning algorithm for Partially Observable Stochastic Games (BA-POSGMCP) algorithm used for the AAMAS paper *Bayes-Adaptive Monte-Carlo Planning for Type-Based Reasoning in Large Partially Observable Environments*.

The **full paper** is available in the ``paper`` subdirectory.

Installation
------------

The library is implemented in ``python 3.8`` and has the following main dependencies:

1. `Pytorch <https://pytorch.org>`_ >=1.11,<2.0
2. `Rllib <https://github.com/ray-project/ray/tree/1.12.0>`_ == 1.12
3. `posggym <https://github.com/RDLLab/posggym/tree/v0.1.0>`_ == 0.1.0
4. `posggym-agents <https://github.com/Jjschwartz/posggym-agents/tree/v0.1.1>`_ == 0.1.1

As with any python package we recomment using a virtual environment (e.g. `Conda <https://docs.conda.io/en/latest/>`_).

**Installation** of ``baposgmcp`` requires cloning the repo then installing using pip:

.. code-block:: bash

    git clone git@github.com:Jjschwartz/ba-posgmcp.git
	cd ba-posgmcp
    pip install -e .


This will install the ``baposgmcp`` package along with the necessary dependencies.

And voila.


The codebase
------------

There are two main parts to the codebase:

1. The ``baposgmcp`` directory containing the ``baposgmcp`` python package
2. The ``experiments`` directory containing scripts and Jupyter notebooks for running and analysing the experiments used in the paper. The results are also store here.


baposgmcp
`````````

The ``baposgmcp`` python package contains a few main parts:

1. ``baselines`` - implementation code for the different baselines used in the paper
2. ``plot`` - code used for generating plots and running analysis
3. ``run`` - code for running and tracking experiments
4. ``tree`` - the implementation of the **BA-POSGMCP** algorithm
5. ``meta-policy.py`` - classes and functions implementing the meta-policy
6. ``policy_prior.py`` - classes and functions implementing the prior over policies

The main implementation of the **BA-POSGMCP** algorithm is contained in the ``baposgmcp/tree/policy.py`` file.

experiments
```````````

This directory contains scripts for running the experiments in each environment as well as Jupyter notebooks for analysing the results and the actual results files.


Results
-------

If you run any of the experiment scripts, by default experiment results are saved to the ``~/baposgmcp_results`` directory.


Questions or Issues
-------------------

If you have any questions or issues please email jonathon.schwartz@anu.edu.au or create an issue in the issue section on github.


Authors
-------

Jonathon Schwartz (primary author and code writer/maintainer) and Hanna Kurniwati

Please Cite
-----------

If you use the code in this repository or the **BA-POSGMCP** algorithm, consider citing::

   @inproceedings{schwartzBayesadaptiveMontecarloPlanning2023,
       title = {Bayes-Adaptive Monte-Carlo Planning for Type-Based Reasoning in Large Partially Observable Environments: Extended Abstract},
       author = {Jonathon Schwartz and Hanna Kurniawati},
       booktitle = {Autonomous Agents and Multiagent Systems (AAMAS)},
       year = {2023},
       code = {https://github.com/Jjschwartz/ba-posgmcp},
   }
