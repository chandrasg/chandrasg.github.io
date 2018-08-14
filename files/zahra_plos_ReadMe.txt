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


If using this data set, please cite the following publication:

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




