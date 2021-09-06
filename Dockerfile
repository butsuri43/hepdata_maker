FROM butsuri43/hepdata_submission_docker
ARG hepdata_maker_tag

# Build the image as root user
USER root

# Install the hepdata_maker from PyPI
COPY . /hepdata_maker_code
RUN cd /hepdata_maker_code && \
    pip3 install . && \
    pip3 list

WORKDIR /