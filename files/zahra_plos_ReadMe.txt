This folder  contains  the following dataset: Crossed-Linked Flickr and Twitter dataset.
	
Psycho-Flickr consists of a set of users who answered the BFI survey. We collected profile and up to 300 posted and liked pictures for each user. Please contact Christina Segalin (http://www.cristinasegalin.com/) for access to these labels.

Crossed-Linked Flickr and Twitter consists of a set of users with active accounts both on Flickr and Twitter.
	We used text mining approaches to predict personality traits for this set of users.
	We collected profile and up to 300 posted and liked picture for each user. 

Twitter or Flickr  user ids with their text-predicted/BFI survey Big-Five personality scores are presented.

Features extracted from profile images and averaged over posted and Liked Images are presented that include :
	Colors Features
	CNN Generic Features: 4096 dim penultimate layer features of VGG_Net
	CNN object and scene categories:VGG_Net prediction on 1000 objects and 365 scene categories
	Imagga tags

Big five personality traits are in this order:
(ope: openness, con: conscientiousness, ext: extraversion, agr: agreeableness, and neu: neuroticism)


For more information/questions about the dataset, please contact Sharath Chandra (chandrasg.github.io)


If using this data set, please cite the following publications (as this dataset has been aggregated from multiple sources):

@article{samani2018cross,
title={Cross-platform and cross-interaction study of user personality based on images on Twitter and Flickr},
author={Samani, Zahra Riahi and Guntuku, Sharath Chandra and Moghaddam, Mohsen Ebrahimi and Preo{\c{t}}iuc-Pietro, Daniel and Ungar, Lyle H},
journal={PloS one},
volume={13},
number={7},
pages={e0198660},
year={2018},
publisher={Public Library of Science}
}

@inproceedings{guntuku2017studying,
title={Studying personality through the content of posted and liked images on Twitter},
author={Guntuku, Sharath Chandra and Lin, Weisi and Carpenter, Jordan and Ng, Wee Keong and Ungar, Lyle H and Preo{\c{t}}iuc-Pietro, Daniel},
booktitle={Proceedings of the 2017 ACM on web science conference},
pages={223--227},
year={2017},
organization={ACM}
}

@article{segalin2017pictures,
title={The pictures we like are our image: continuous mapping of favorite pictures into self-assessed and attributed personality traits},
author={Segalin, Crisitina and Perina, Alessandro and Cristani, Marco and Vinciarelli, Alessandro},
journal={IEEE Transactions on Affective Computing},
volume={8},
number={2},
pages={268--285},
year={2017},
publisher={IEEE}
}

@article{guntuku2016likes,
title={Who likes What, and Why? Insights into Personality Modeling based on ImageLikes'},
author={Guntuku, Sharath Chandra and Zhou, Joey T and Roy, Sujoy and Weisi, Lin and Tsang, Ivor W},
journal={IEEE Transactions on Affective Computing},
year={2016},
publisher={IEEE}
}




